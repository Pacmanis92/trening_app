import flet as ft

from trainbeast.database import make_engine, make_session_factory
from trainbeast.services import TrainingService
from trainbeast.ui import TrainBeastApp


def main(page: ft.Page):
    service = TrainingService(make_session_factory(make_engine()))
    TrainBeastApp(page, service)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
