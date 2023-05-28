import sys
import requests
import json
import time
import logging
import markdown
import configparser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, QWidget, QLabel, QMenu, QInputDialog, QLineEdit, QDialog, QComboBox, QTextBrowser)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal

logging.basicConfig(filename='app.log', level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

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
        response.raise_for_status()
    except requests.exceptions.RequestException as err:
        logging.warning(f"Request sending error: {err}")
        return f"可能触发150s超时或其他原因，目前请求发送错误: {err}"
    
    try:
        json_response = response.json()
    except json.JSONDecodeError as err:
        logging.warning(f"Cannot parse JSON response: {err}")
        return f"无法解析JSON响应: {err}"
    
    if 'choices' in json_response and json_response['choices']:
        return json_response['choices'][0]['message']['content']
    else:
        logging.warning("响应中没有 'choices' 键或 'choices' 为空")
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

class ChangeSettingsDialog(QDialog):
    def __init__(self, title, label_text, default_text, settings_key, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        layout = QVBoxLayout()

        label = QLabel(label_text)
        layout.addWidget(label)

        self.line_edit = QLineEdit()
        self.line_edit.setText(default_text)
        layout.addWidget(self.line_edit)

        button = QPushButton("提交修改")
        button.clicked.connect(self.update_setting)
        layout.addWidget(button)

        self.setLayout(layout)

        self.settings_key = settings_key
        self.parent = parent

    def update_setting(self):
        try:
            new_value = self.line_edit.text()
            self.parent.config.set('Settings', self.settings_key, new_value)
            with open('GPT-Config.ini', 'w') as configfile:
                self.parent.config.write(configfile)
            self.parent.update_settings()
            self.close()
        except Exception as e:
            logging.warning(f"Error updating setting in ChangeSettingsDialog: {e}")
            self.close()


class ModelSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模型设置")

        layout = QVBoxLayout()

        label = QLabel("请选择使用的模型：")
        layout.addWidget(label)

        self.combo_box = QComboBox()
        self.model_mapping = {
            'GPT-3.5': 'text-davinci-002-render-sha',
            'GPT-3.5 Mobile': 'text-davinci-002-render-sha-mobile',
            'GPT-4 Mobile': 'gpt-4-mobile',
            'GPT-4': 'gpt-4',
            'GPT-4 Browsing': 'gpt-4-browsing',
            'GPT-4 Plugins': 'gpt-4-plugins',
            '自定义': '自定义',
        }
        self.combo_box.addItems(list(self.model_mapping.keys()))
        self.combo_box.currentIndexChanged.connect(self.update_model)
        layout.addWidget(self.combo_box)

        self.line_edit = QLineEdit()
        layout.addWidget(self.line_edit)

        button = QPushButton("提交修改")
        button.clicked.connect(self.update_setting)
        layout.addWidget(button)

        self.setLayout(layout)

        self.parent = parent

    def update_model(self, index):
        if self.combo_box.currentText() == "自定义":
            self.line_edit.setEnabled(True)
        else:
            self.line_edit.setEnabled(False)

    def update_setting(self):
        try:
            if self.combo_box.currentText() == "自定义":
                new_value = self.line_edit.text()
            else:
                new_value = self.model_mapping[self.combo_box.currentText()]
            self.parent.config.set('Settings', 'model', new_value)
            with open('GPT-Config.ini', 'w') as configfile:
                self.parent.config.write(configfile)
            self.parent.update_settings()
            self.close()
        except Exception as e:
            logging.warning(f"Error updating setting in ModelSettingsDialog: {e}")
            self.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("快速向GPT提问")

        self.config = configparser.ConfigParser()
        self.update_settings()

        layout = QVBoxLayout()

        self.question_text = QTextEdit()
        layout.addWidget(self.question_text)

        self.submit_button = QPushButton('提交')
        self.submit_button.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_button)

        self.result_text = QTextBrowser()  
        layout.addWidget(self.result_text)

        self.time_label = QLabel()
        layout.addWidget(self.time_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)

        menuBar = self.menuBar()
        settings_menu = QMenu('设置', self)
        menuBar.addMenu(settings_menu)

        settings_menu.addAction('更改请求URL', self.change_url)
        settings_menu.addAction('更改认证信息', self.change_auth)
        settings_menu.addAction('自定义模型', self.change_model)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def change_url(self):
        default_url = self.settings['url']
        dialog = ChangeSettingsDialog("设置请求URL", "请输入新的请求URL：", default_url, "url", self)
        dialog.exec()

    def change_auth(self):
        default_auth = self.settings['auth']
        dialog = ChangeSettingsDialog("设置认证信息", "请输入新的认证信息：", default_auth, "auth", self)
        dialog.exec()

    def change_model(self):
        dialog = ModelSettingsDialog(self)
        dialog.exec()

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
        self.result_text.setHtml(markdown.markdown(response)) 

    def update_settings(self):
        try:
            self.config.read('GPT-Config.ini')
            self.settings = {'url': self.config.get('Settings', 'url', fallback="http://127.0.0.1:31480/v1/chat/completions"),
                             'auth': self.config.get('Settings', 'auth', fallback="TotallySecurePassword"),
                             'model': self.config.get('Settings', 'model', fallback="gpt-4-mobile")}
        except Exception as e:
            logging.warning(f"Error updating settings in MainWindow: {e}") 




app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
