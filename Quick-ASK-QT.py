import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, QWidget, QLabel, QMenu, QInputDialog, QMenuBar, QGridLayout, QComboBox, QDialog, QLineEdit, QDialogButtonBox
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction
import requests
import json
import time

def send_request(content, url, auth, model):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': auth
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": content}]
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=150)
        response.raise_for_status()  # 将在HTTP错误时引发异常
    except requests.exceptions.RequestException as err:
        return f"触发150s超时，请求发送错误: {err}"
    
    try:
        json_response = response.json()
    except json.JSONDecodeError as err:
        return f"无法解析JSON响应: {err}"
    
    if 'choices' in json_response and json_response['choices']:
        return json_response['choices'][0]['message']['content']
    else:
        return "响应中没有 'choices' 键或 'choices' 为空"

class SendRequestThread(QThread):
    finished = pyqtSignal(str)
    def __init__(self, content, url, auth, model):
        QThread.__init__(self)
        self.content = content
        self.url = url
        self.auth = auth
        self.model = model
    def run(self):
        response = send_request(self.content, self.url, self.auth, self.model)
        self.finished.emit(response)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("快速向GPT提问")

        layout = QVBoxLayout()

        self.question_text = QTextEdit()
        layout.addWidget(self.question_text)

        self.submit_button = QPushButton('提交')
        self.submit_button.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_button)

        self.result_text = QTextEdit()
        layout.addWidget(self.result_text)

        self.time_label = QLabel()
        layout.addWidget(self.time_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)

        self.settings = {'url': "http://127.0.0.1:31480/v1/chat/completions", 'auth': "TotallySecurePassword", 'model': "gpt-4-mobile"}
        menuBar = self.menuBar()
        settings_menu = QMenu('设置', self)
        menuBar.addMenu(settings_menu)

        settings_menu.addAction(QAction('更改请求URL', self, triggered=self.change_url))
        settings_menu.addAction(QAction('更改认证信息', self, triggered=self.change_auth))
        settings_menu.addAction(QAction('自定义模型', self, triggered=self.change_model))

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def change_url(self):
        url, ok = QInputDialog.getText(self, '更改请求URL', '请输入新的请求URL：', QLineEdit.Normal, self.settings['url'])
        if ok:
            self.settings['url'] = url
    
    def change_auth(self):
        auth, ok = QInputDialog.getText(self, '更改认证信息', '请输入新的认证信息：', QLineEdit.Normal, self.settings['auth'])
        if ok:
            self.settings['auth'] = auth

    def change_model(self):
        model, ok = QInputDialog.getText(self, '自定义模型', '请输入新的模型名：', QLineEdit.Normal, self.settings['model'])
        if ok:
            self.settings['model'] = model

    def update_time(self):
        elapsed_time = time.time() - self.start_time
        self.time_label.setText(f'已用时: {elapsed_time:.1f} 秒')

    def on_submit(self):
        self.result_text.clear()
        content = self.question_text.toPlainText()

        self.thread = SendRequestThread(content, self.settings['url'], self.settings['auth'], self.settings['model'])
        self.thread.finished.connect(self.on_result)
        self.thread.start()

        self.start_time = time.time()
        self.timer.start(100)

    def on_result(self, response):
        self.timer.stop()
        self.result_text.setPlainText(response)

app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()