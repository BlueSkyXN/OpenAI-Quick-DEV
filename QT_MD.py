import sys
from PyQt6.QtWidgets import QApplication, QTextBrowser
import markdown

class MainWindow(QTextBrowser):
    def __init__(self):
        super().__init__()

        # Markdown text
        md_text = """
# Hello

This is some **Markdown** text.
- First item
- Second item
        """

        # Convert Markdown to HTML
        html = markdown.markdown(md_text)

        # Display HTML in QTextBrowser
        self.setHtml(html)

app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
