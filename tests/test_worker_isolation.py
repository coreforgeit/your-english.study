import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NON_WORKER_PACKAGES = (
    'ai',
    'api',
    'bot',
    'core',
    'services',
    'task_queue',
)


class WorkerIsolationTest(unittest.TestCase):
    def test_runtime_packages_do_not_import_worker(self) -> None:
        forbidden_imports: list[str] = []

        for package_name in NON_WORKER_PACKAGES:
            for path in (PROJECT_ROOT / package_name).rglob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    imported_modules: list[str] = []
                    if isinstance(node, ast.Import):
                        imported_modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported_modules = [node.module]

                    if any(
                        module == 'worker' or module.startswith('worker.')
                        for module in imported_modules
                    ):
                        forbidden_imports.append(str(path.relative_to(PROJECT_ROOT)))

        self.assertEqual(forbidden_imports, [])

    def test_only_worker_service_mounts_worker_package(self) -> None:
        compose = (
            PROJECT_ROOT / 'docker' / 'docker-compose.yml'
        ).read_text(encoding='utf-8')

        self.assertEqual(compose.count('../worker:/app/worker'), 1)

    def test_api_and_bot_images_do_not_copy_worker_package(self) -> None:
        dockerfiles = (
            PROJECT_ROOT / 'docker' / 'dockerfiles' / 'api.prod.Dockerfile',
            PROJECT_ROOT / 'docker' / 'dockerfiles' / 'bot.prod.Dockerfile',
        )

        for dockerfile in dockerfiles:
            content = dockerfile.read_text(encoding='utf-8')
            with self.subTest(dockerfile=dockerfile.name):
                self.assertNotIn('COPY . .', content)
                self.assertNotIn('COPY worker', content)
