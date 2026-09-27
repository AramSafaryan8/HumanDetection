from core.vision_worker import VisionWorker
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from ui.banner_overlay import BannerOverlay

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Human detection")
        
        self.resize(1280, 720)

        camera_panel = QWidget()
        camera_layout = QVBoxLayout(camera_panel)

        self.camera_label = QLabel("Initializing Camera Preview...")

        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet(
            "background-color: #222222; color: #ffffff; border: 2px solid #444444; border-radius: 10px;"
        )

        self.camera_label.setMinimumSize(480, 360)
        camera_layout.addWidget(self.camera_label)

        main_layout = QHBoxLayout()

        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        main_layout.addWidget(camera_panel, stretch = 2)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self.banner = BannerOverlay(central_widget)

        self.vision_worker = VisionWorker(camera_id=0)
        self.vision_worker.frame_signal.connect(self.update_frame)
        self.vision_worker.notification_signal.connect(self.banner.show_message)
        self.vision_worker.error_signal.connect(self.banner.show_error)
        self.vision_worker.start()

    def update_frame(self, qt_image):
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.camera_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.camera_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.banner.reposition()

    def closeEvent(self, event):
        self.vision_worker.stop()
        event.accept()