"""Preparacao portavel: orientacoes e criacao segura do .env, sem acesso a nuvem."""
import argparse
import os
import platform

from scripts import check_environment
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def instructions(system: str) -> str:
    common = (
        'Minimos: Python 3.12+, Terraform 1.16+, Confluent CLI 4.81+.\n'
        'Terraform: https://developer.hashicorp.com/terraform/install\n'
        'Confluent CLI: https://docs.confluent.io/confluent-cli/current/install.html\n'
        'Use somente fontes oficiais e valide checksums quando fornecidos.\n'
    )
    steps = {
        'Windows': (
            'Windows/PowerShell: baixe os ZIPs oficiais correspondentes a sua arquitetura; '
            'extraia os executaveis para diretorios persistentes, adicione esses diretorios '
            'ao PATH de usuario e abra novo PowerShell.\n'
            'Confluent ZIP: https://github.com/confluentinc/cli/releases/latest\n'
        ),
        'Darwin': (
            'macOS/Homebrew: brew tap hashicorp/tap\n'
            'brew install hashicorp/tap/terraform\n'
            'brew install confluentinc/tap/cli\n'
        ),
        'Linux': (
            'Linux: siga os repositorios oficiais HashiCorp e Confluent para APT/YUM, '
            'ou os binarios correspondentes a distribuicao e arquitetura.\n'
        ),
    }.get(system, 'Sistema nao reconhecido; consulte a compatibilidade oficial.\n')
    return (
        common + steps +
        'Verifique: terraform version ; confluent version\n'
        'Cheque o ambiente: python -m scripts.check_environment\n'
        'Crie .env local: python -m scripts.bootstrap_local init-env\n'
        'Nenhum comando deste assistente instala software, acessa nuvem ou faz login.'
    )



def repair_tools(system: str | None = None) -> bool:
    """Diagnostico de recuperacao: nao instala, altera PATH ou acessa rede.

    A verificaçao usa o mesmo parser/limites do preflight para nao divergir
    em ambientes Windows, Linux ou macOS.
    """
    system = system or platform.system()
    print("=== TOOL RECOVERY (READ ONLY) ===")
    print(f"OS={system}")
    status = {}
    for name, executable, args, field, minimum in (
        ("TERRAFORM", "terraform", ["version", "-json"], "terraform_version", check_environment.MIN_TERRAFORM),
        ("CONFLUENT_CLI", "confluent", ["version"], None, check_environment.MIN_CONFLUENT),
    ):
        found = check_environment.tool_version(executable, args, field)
        status[name] = check_environment.check_status(found, minimum)
        print(f"{name}_STATUS={status[name]}")
        print(f"{name}_MIN_VERSION={'.'.join(map(str, minimum))}")
    print("CLOUD_CALLS=False")
    print("INSTALLATION_PERFORMED=False")
    print("CREDENTIAL_VALUES_PRINTED=False")
    print("NEXT_ACTIONS_BEGIN")
    if all(value == "OK" for value in status.values()):
        print("Todas as CLIs atendem aos minimos; execute python -m scripts.check_environment")
    else:
        print(instructions(system))
        if system == 'Windows':
            print('Windows: localize executaveis com Get-Command terraform,confluent -ErrorAction SilentlyContinue')
            print('Windows: se ja instalados, adicione as pastas dos executaveis ao PATH do usuario em Configuracoes > Variaveis de Ambiente e abra novo terminal.')
            print('Windows: confirme com Get-Command terraform e Get-Command confluent; nao adicione arquivos individuais ao PATH.')
        elif system in ('Darwin', 'Linux'):
            print('macOS/Linux: localize executaveis com command -v terraform; command -v confluent')
            print('macOS/Linux: configure PATH para conter os DIRETORIOS de instalacao e abra novo terminal.')
        print('Reexecute: python -m scripts.bootstrap_local repair-tools')
    print("NEXT_ACTIONS_END")
    return all(value == "OK" for value in status.values())


def init_env(root: Path = ROOT) -> bool:
    """Copia modelo sem sobrescrever .env; nao mostra conteudos ou segredos."""
    source, dest = root / '.env.example', root / '.env'
    if source.is_symlink() or not source.is_file():
        raise RuntimeError('Modelo .env.example ausente ou invalido.')
    # O_EXCL bloqueia sobrescrita mesmo quando duas instancias rodam em paralelo.
    try:
        fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print('ENV_ALREADY_EXISTS=True')
        return False
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(source.read_bytes())
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    print('ENV_CREATED=True; preencha localmente, nunca publique credenciais.')
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('instructions', 'init-env', 'repair-tools'), nargs='?', default='instructions')
    args = parser.parse_args(argv)
    if args.action == 'instructions':
        print(instructions(platform.system()))
        return 0
    if args.action == 'repair-tools':
        return 0 if repair_tools() else 1
    try:
        init_env()
    except (OSError, RuntimeError):
        # Mensagem fixa evita vazamento de caminhos, valores e metadados privados.
        print('ENV_CREATION_FAILED=True; revise modelo e permissoes locais.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
