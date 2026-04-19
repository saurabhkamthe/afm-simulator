import sys
from PyQt6.QtWidgets import QApplication
from ev_motor_sim.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EV Motor Simulator")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
