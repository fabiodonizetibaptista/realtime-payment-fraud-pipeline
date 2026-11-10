"""Preparacao portavel: orientacoes e criacao segura do .env, sem acesso a nuvem."""
import argparse
import os
import platform
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
    parser.add_argument('action', choices=('instructions', 'init-env'), nargs='?', default='instructions')
    args = parser.parse_args(argv)
    if args.action == 'instructions':
        print(instructions(platform.system()))
        return 0
    try:
        init_env()
    except (OSError, RuntimeError):
        # Mensagem fixa evita vazamento de caminhos, valores e metadados privados.
        print('ENV_CREATION_FAILED=True; revise modelo e permissoes locais.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
