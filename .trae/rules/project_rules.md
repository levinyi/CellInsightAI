1. 请保持对话语言为中文/英文
2. 这个项目的系统为 Ubuntu 20.04
3. 虚拟环境这样激活：source .venv/bin/activate
4. 请在生成代码时添加函数级注释
5. 项目启动用这个命令：fuser -k 8011/tcp || true; python manage.py runserver 192.168.3.185:8011
6. 写每个html页面的时候都要注意国际化，英文和中文要处理好
7. 写每个html页面的时候都要注意 light 和dark 两个主题，要适配。