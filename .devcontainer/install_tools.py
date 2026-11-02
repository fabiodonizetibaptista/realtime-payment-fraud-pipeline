"""Instala versoes reproduziveis do Terraform e da Confluent CLI no Codespace."""

import hashlib
import json
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TERRAFORM_VERSION = "1.16.2"
CONFLUENT_VERSION = "4.81.0"
CONFLUENT_SHA256 = {
    "amd64": "5e1039c65043f8d9497cb1b200cdd807524c861e0391a856342e3f2eb8c9f55c",
    "arm64": "a0ad83bcafb106b2d9cb2d406cf1a475f10a47ecd6681a4a53e65ea2fa30498c",
}


def version_parts(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(int(part) for part in match.groups()) if match else None


def installed_version(command: str, args: list[str], json_key: str | None = None) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run([command, *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if result.returncode:
        return None
    output = result.stdout + result.stderr
    if json_key:
        try:
            output = json.loads(result.stdout).get(json_key, "")
        except json.JSONDecodeError:
            return None
    return version_parts(output)


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "realtime-payment-fraud-pipeline"})
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def architecture() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    raise RuntimeError(f"Arquitetura Linux nao suportada: {machine}.")


def install_terraform(arch: str) -> None:
    minimum = version_parts(TERRAFORM_VERSION)
    current = installed_version("terraform", ["version", "-json"], "terraform_version")
    if current and current >= minimum:
        print("Terraform ja disponivel; versao minima atendida.")
        return

    filename = f"terraform_{TERRAFORM_VERSION}_linux_{arch}.zip"
    base_url = f"https://releases.hashicorp.com/terraform/{TERRAFORM_VERSION}"
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        archive = work / filename
        checksums = work / "SHA256SUMS"
        download(f"{base_url}/{filename}", archive)
        download(f"{base_url}/terraform_{TERRAFORM_VERSION}_SHA256SUMS", checksums)
        expected = next(
            (parts[0] for line in checksums.read_text(encoding="utf-8").splitlines()
             if len(parts := line.split()) == 2 and parts[1] == filename),
            None,
        )
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if not expected or actual != expected:
            raise RuntimeError("Checksum do Terraform invalido.")
        with zipfile.ZipFile(archive) as bundle:
            binary = work / "terraform"
            binary.write_bytes(bundle.read("terraform"))
        subprocess.run(["sudo", "install", "-m", "0755", str(binary), "/usr/local/bin/terraform"], check=True)
    print(f"Terraform {TERRAFORM_VERSION} instalado e checksum validado.")


def install_confluent(arch: str) -> None:
    minimum = version_parts(CONFLUENT_VERSION)
    current = installed_version("confluent", ["version"])
    if current and current >= minimum:
        print("Confluent CLI ja disponivel; versao minima atendida.")
        return

    filename = f"confluent-cli_{CONFLUENT_VERSION}_{arch}.deb"
    url = f"https://github.com/confluentinc/cli/releases/download/v{CONFLUENT_VERSION}/{filename}"
    with tempfile.TemporaryDirectory() as directory:
        package = Path(directory) / filename
        download(url, package)
        actual = hashlib.sha256(package.read_bytes()).hexdigest()
        if actual != CONFLUENT_SHA256[arch]:
            raise RuntimeError("Checksum da Confluent CLI invalido.")
        subprocess.run(["sudo", "dpkg", "-i", str(package)], check=True)
    print(f"Confluent CLI {CONFLUENT_VERSION} instalada e checksum validado.")


def main() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("Este instalador e destinado ao Linux do GitHub Codespaces.")
    if not shutil.which("sudo") or not shutil.which("dpkg"):
        raise RuntimeError("O ambiente Codespaces precisa disponibilizar sudo e dpkg.")
    arch = architecture()
    install_terraform(arch)
    install_confluent(arch)


if __name__ == "__main__":
    main()
