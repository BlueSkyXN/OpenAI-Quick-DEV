import requests
import json
from tkinter import Tk, Entry, Button, StringVar, Label



def send_request(content):
    url = 'http://api.chatgpt.com/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Password'
    }
    data = {
        "model": "gpt-4-mobile",
        "messages": [{"role": "user", "content": content}]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    json_response = response.json()
    return json_response['choices'][0]['message']['content']


def on_button_click(entry, text_var):
    content = entry.get()
    response = send_request(content)
    text_var.set("GPT: " + response)


def create_window():
    window = Tk()
    window.title("快速向GPT提问")
    window.geometry("400x200")  # 将窗口的宽度设置为600像素，高度为200像素
    text_var = StringVar()
    title_label = Label(window, text="请输入您的问题：")
    title_label.pack(pady=10)
    entry = Entry(window)
    entry.pack(pady=10)
    button = Button(window, text='提问', command=lambda: on_button_click(entry, text_var))
    button.pack(pady=10)
    label = Label(window, textvariable=text_var)
    label.pack(pady=10)
    window.mainloop()

if __name__ == "__main__":
    create_window()
