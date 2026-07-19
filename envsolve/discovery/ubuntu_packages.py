from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
from pathlib import PurePosixPath
import re
import shlex
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from envsolve.context.models import normalize_packages, validate_name
from envsolve.discovery.apt_file import AptFileCandidate, ProviderEnvironment


PACKAGE_LINK = re.compile(r"^/([^/]+)/([^/]+)$")
ENDPOINT = "https://packages.ubuntu.com/search"


class _ContentsTableParser(HTMLParser):
    def __init__(self, suite: str) -> None:
        super().__init__(convert_charrefs=True)
        self.suite = suite
        self.rows: list[tuple[str, tuple[str, ...]]] = []
        self._in_row = False
        self._in_file = False
        self._file_parts: list[str] = []
        self._packages: list[str] = []
        self._package_parts: list[str] | None = None
        self.saw_html_end = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self._in_row = True
            self._file_parts = []
            self._packages = []
        elif tag == "td" and self._in_row:
            classes = set((attributes.get("class") or "").split())
            self._in_file = "file" in classes
        elif tag == "a" and self._in_row and not self._in_file:
            href = attributes.get("href") or ""
            match = PACKAGE_LINK.fullmatch(href)
            if match is not None and match.group(1) == self.suite:
                self._package_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_file:
            self._file_parts.append(data)
        elif self._package_parts is not None:
            self._package_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._package_parts is not None:
            package = "".join(self._package_parts).strip()
            if package:
                self._packages.append(package)
            self._package_parts = None
        elif tag == "td":
            self._in_file = False
        elif tag == "tr" and self._in_row:
            path = "".join(self._file_parts).strip()
            if path and self._packages:
                self.rows.append((path, tuple(self._packages)))
            self._in_row = False
            self._file_parts = []
            self._packages = []
        elif tag == "html":
            self.saw_html_end = True


@dataclass(frozen=True)
class UbuntuContentsResponse:
    request_url: str
    final_url: str
    status: int
    byte_count: int
    sha256: str
    body: str

    def provenance(self) -> dict[str, Any]:
        return {
            "request_url": self.request_url,
            "final_url": self.final_url,
            "status": self.status,
            "bytes": self.byte_count,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class UbuntuContentsDiscovery:
    capability: str
    suite: str
    architecture: str
    candidates: tuple[AptFileCandidate, ...]
    rejected: tuple[dict[str, str], ...]
    response: UbuntuContentsResponse

    @property
    def packages(self) -> tuple[str, ...]:
        if not self.candidates:
            return ()
        return tuple(normalize_packages([item.package for item in self.candidates]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "suite": self.suite,
            "architecture": self.architecture,
            "manager": "apt-get",
            "packages": list(self.packages),
            "candidates": [
                {"package": item.package, "path": item.path}
                for item in self.candidates
            ],
            "rejected": list(self.rejected),
            "response": self.response.provenance(),
        }


def build_ubuntu_contents_command(
    capability: str,
    suite: str,
    architecture: str,
    timeout_seconds: int,
    max_response_bytes: int,
    user_agent: str,
) -> str:
    name = validate_name(capability, "capability")
    release = validate_name(suite, "suite")
    arch = validate_name(architecture, "architecture")
    if not 1 <= timeout_seconds <= 300:
        raise ValueError("HTTP timeout must be between 1 and 300 seconds")
    if not 1024 <= max_response_bytes <= 100_000:
        raise ValueError("Response byte limit is outside the allowed range")
    query = urlencode(
        {
            "searchon": "contents",
            "keywords": name,
            "mode": "exactfilename",
            "suite": release,
            "arch": arch,
        }
    )
    url = f"{ENDPOINT}?{query}"
    program = (
        "import hashlib,json,sys,urllib.request;"
        "url,timeout,limit,agent=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4];"
        "request=urllib.request.Request(url,headers={'User-Agent':agent});"
        "response=urllib.request.urlopen(request,timeout=timeout);"
        "body=response.read(limit+1);"
        "len(body)<=limit or (_ for _ in ()).throw(ValueError('response too large'));"
        "text=body.decode('utf-8');"
        "print(json.dumps({'request_url':url,'final_url':response.geturl(),"
        "'status':response.status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),"
        "'body':text},ensure_ascii=True,separators=(',',':')))"
    )
    return " ".join(
        shlex.quote(value)
        for value in (
            "python",
            "-c",
            program,
            url,
            str(timeout_seconds),
            str(max_response_bytes),
            user_agent,
        )
    )


def parse_ubuntu_contents_response(
    stdout: str,
    capability: str,
    environment: ProviderEnvironment,
    max_response_bytes: int,
) -> UbuntuContentsDiscovery:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Ubuntu Contents response envelope is invalid") from exc
    if not isinstance(value, dict) or not isinstance(value.get("body"), str):
        raise ValueError("Ubuntu Contents response envelope is incomplete")
    request_url = str(value.get("request_url", ""))
    final_url = str(value.get("final_url", ""))
    status = value.get("status")
    byte_count = value.get("bytes")
    digest = str(value.get("sha256", ""))
    body = value["body"]
    if status != 200 or isinstance(byte_count, bool) or not isinstance(byte_count, int):
        raise ValueError("Ubuntu Contents HTTP result is invalid")
    encoded = body.encode("utf-8")
    if byte_count != len(encoded) or byte_count > max_response_bytes:
        raise ValueError("Ubuntu Contents response size is invalid")
    if hashlib.sha256(encoded).hexdigest() != digest:
        raise ValueError("Ubuntu Contents response hash is invalid")
    request = urlparse(request_url)
    final = urlparse(final_url)
    if (
        request.scheme != "https"
        or request.hostname != "packages.ubuntu.com"
        or request.path != "/search"
        or final.scheme != "https"
        or final.hostname != "packages.ubuntu.com"
        or final.path != "/search"
    ):
        raise ValueError("Ubuntu Contents request escaped the fixed HTTPS endpoint")
    query = parse_qs(request.query, strict_parsing=True)
    name = validate_name(capability, "capability")
    expected = {
        "searchon": ["contents"],
        "keywords": [name],
        "mode": ["exactfilename"],
        "suite": [environment.codename],
        "arch": [environment.architecture],
    }
    if query != expected or parse_qs(final.query, strict_parsing=True) != expected:
        raise ValueError("Ubuntu Contents request parameters changed")
    parser = _ContentsTableParser(environment.codename)
    parser.feed(body)
    parser.close()
    if not parser.saw_html_end:
        raise ValueError("Ubuntu Contents HTML response is truncated")
    path_directories = set(environment.path)
    candidates: set[AptFileCandidate] = set()
    rejected: list[dict[str, str]] = []
    for path_value, packages in parser.rows:
        path = PurePosixPath(path_value)
        for package in packages:
            if not path.is_absolute():
                rejected.append(
                    {"package": package, "path": path_value, "reason": "non_absolute"}
                )
            elif path.name != name:
                rejected.append(
                    {"package": package, "path": str(path), "reason": "basename"}
                )
            elif str(path.parent) not in path_directories:
                rejected.append(
                    {"package": package, "path": str(path), "reason": "not_on_path"}
                )
            else:
                normalize_packages([package])
                candidates.add(AptFileCandidate(package, str(path)))
    return UbuntuContentsDiscovery(
        capability=name,
        suite=environment.codename,
        architecture=environment.architecture,
        candidates=tuple(sorted(candidates)),
        rejected=tuple(sorted(rejected, key=lambda item: tuple(sorted(item.items())))),
        response=UbuntuContentsResponse(
            request_url=request_url,
            final_url=final_url,
            status=status,
            byte_count=byte_count,
            sha256=digest,
            body=body,
        ),
    )
