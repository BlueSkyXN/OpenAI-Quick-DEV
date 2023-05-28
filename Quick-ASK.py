import requests
import json
import threading
import time
from tkinter import Tk, Text, Button, StringVar, Label, Menu, Toplevel, END, Scrollbar, Entry, OptionMenu, Y, BOTH, Frame, RIGHT, LEFT

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



def create_url_settings_window(url_var):
    url_settings_window = Toplevel()
    url_settings_window.title("设置请求URL")
    url_settings_window.geometry("500x200")
    Label(url_settings_window, text="请输入请求的URL：").pack(pady=5)
    Label(url_settings_window, text="默认的Endpoint端点是 /v1/chat/completions").pack(pady=5)
    current_url_label = Label(url_settings_window, textvariable=url_var)
    current_url_label.pack(pady=5)
    new_url_var = StringVar()
    url_entry = Entry(url_settings_window, textvariable=new_url_var, width=50)
    url_entry.pack(pady=5)
    Button(url_settings_window, text='提交修改', command=lambda: [url_var.set(new_url_var.get()), url_settings_window.destroy()]).pack(pady=10)


def create_auth_settings_window(auth_var):
    auth_settings_window = Toplevel()
    auth_settings_window.title("设置认证信息")
    auth_settings_window.geometry("500x200")
    Label(auth_settings_window, text="请输入请求的认证信息（Authorization）：").pack(pady=5)
    Label(auth_settings_window, text="FAKEAPI默认的认证信息是 TotallySecurePassword").pack(pady=5)
    current_auth_label = Label(auth_settings_window, textvariable=auth_var)
    current_auth_label.pack(pady=5)
    new_auth_var = StringVar()
    auth_entry = Entry(auth_settings_window, textvariable=new_auth_var, width=50)
    auth_entry.pack(pady=5)
    Button(auth_settings_window, text='提交修改', command=lambda: [auth_var.set(new_auth_var.get()), auth_settings_window.destroy()]).pack(pady=10)


def create_model_settings_window(model_var):
    settings_window = Toplevel()
    settings_window.title("模型设置")
    settings_window.geometry("500x200")

    settings_window.columnconfigure(0, weight=1)  # center all elements

    Label(settings_window, text="请选择使用的模型：").grid(row=0, padx=10, pady=10)

    current_model_label = Label(settings_window, textvariable=model_var)
    current_model_label.grid(row=1, padx=10, pady=5)

    model_mapping = {
        'GPT-3.5': 'text-davinci-002-render-sha',
        'GPT-3.5 Mobile': 'text-davinci-002-render-sha-mobile',
        'GPT-4 Mobile': 'gpt-4-mobile',
        'GPT-4': 'gpt-4',
        'GPT-4 Browsing': 'gpt-4-browsing',
        'GPT-4 Plugins': 'gpt-4-plugins',
        '自定义': '自定义',
    }

    # Flip the model_mapping for reverse lookup
    reverse_model_mapping = {v: k for k, v in model_mapping.items()}

    display_var = StringVar()
    display_var.set(reverse_model_mapping[model_var.get()])  # Load the previous setting

    custom_model_var = StringVar()

    if model_var.get() == "自定义":
        custom_model_var.set(model_var.get())

    custom_model_entry = Entry(settings_window, textvariable=custom_model_var, width=50)
    custom_model_entry.grid(row=3, padx=10, pady=10)
    custom_model_entry.grid_remove()  # Initially hide the entry box

    def update_entry(option):
        if option == '自定义':
            custom_model_entry.grid()
            model_var.set(custom_model_var.get())
        else:
            custom_model_entry.grid_remove()
            model_var.set(model_mapping[option])  # Update the model name immediately

    model_menu = OptionMenu(settings_window, display_var, *model_mapping.keys(), command=update_entry)
    model_menu.grid(row=2, padx=10, pady=10)

    Button(settings_window, text='提交修改', command=lambda: submit_model_changes(settings_window, model_var, custom_model_var)).grid(row=4, padx=10, pady=10)


def submit_model_changes(settings_window, model_var, custom_model_var):
    if custom_model_var.get():
        model_var.set(custom_model_var.get())
    settings_window.destroy()


def create_window():
    window = Tk()
    window.title("快速向GPT提问")
    window.geometry("600x400")  # 修改一下窗口大小

    url_var = StringVar()
    url_var.set("http://127.0.0.1:31480/v1/chat/completions")
    auth_var = StringVar()
    auth_var.set("TotallySecurePassword")
    model_var = StringVar()  
    model_var.set("gpt-4-mobile")  

    title_label = Label(window, text="请输入您的问题：")
    title_label.pack(pady=10)
    entry = Text(window, width=60, height=5)
    entry.pack(pady=10)

    button_frame = Frame(window)
    button_frame.pack(pady=10)

    window.button = Button(button_frame, text='提问', command=lambda: on_button_click(window, entry, url_var.get(), auth_var.get(), model_var.get()))
    window.button.pack(pady=10, side=LEFT)

    window.time_label = Label(button_frame, text="请求耗时：")
    window.time_label.pack(pady=10, side=RIGHT)

    result_frame = Frame(window)
    result_frame.pack(pady=10, fill=BOTH, expand=True)

    scrollbar = Scrollbar(result_frame)
    scrollbar.pack(side=RIGHT, fill=Y)
    
    window.result_text = Text(result_frame, wrap="word", yscrollcommand=scrollbar.set)
    window.result_text.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.config(command=window.result_text.yview)

    menubar = Menu(window)
    settings_menu = Menu(menubar, tearoff=0)
    settings_menu.add_command(label="更改请求URL", command=lambda: create_url_settings_window(url_var))
    settings_menu.add_command(label="更改认证信息", command=lambda: create_auth_settings_window(auth_var))
    settings_menu.add_command(label="自定义模型", command=lambda: create_model_settings_window(model_var))
    menubar.add_cascade(label="设置", menu=settings_menu)
    window.config(menu=menubar)

    window.mainloop()



def on_button_click(window, entry, url, auth, model):
    content = entry.get("1.0", END).strip()  # 获取文本框的全部内容

    def update_result_text(response):
        window.result_text.delete("1.0", END)
        window.result_text.insert(END, response)

    def send_request_thread():
        start_time = time.time()
        response = send_request(content, url, auth, model)
        formatted_response = "GPT: " + response
        window.after(0, update_result_text, formatted_response)
        window.button['text'] = "提问"  # change the button text back when the request finishes

        # stop the timer
        window.is_requesting = False

    def timer_thread():
        start_time = time.time()
        while window.is_requesting:
            elapsed_time = time.time() - start_time
            window.time_label['text'] = "请求耗时：{:.3f}s".format(elapsed_time)
            time.sleep(0.1)  # update every 100ms

    # indicate that a request is in progress
    window.is_requesting = True
    window.button['text'] = "提问中..."

    threading.Thread(target=send_request_thread).start()
    threading.Thread(target=timer_thread).start()


if __name__ == "__main__":
    create_window()
