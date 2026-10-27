# 云主机部署说明

目标：把 `EduXJY` 部署到 `121.40.192.55`，hostname 改为 `xiaojunyang`，Nginx 将公网 80 端口反向代理到 Gunicorn，用户可以直接访问 Django 页面。

> 部署前先备份已有 Nginx 配置和数据库。当前 80 端口已有 Nginx 服务并返回 502，因此只新增与公网 IP 精确匹配的 server block，不删除已有 default 站点。

## 1. 连接与预检

```bash
ssh root@121.40.192.55
hostnamectl
cat /etc/os-release
python3 --version
nginx -v
nginx -T > /root/nginx-before-eduxjy.txt
ss -ltnp
df -h
getenforce 2>/dev/null || true
```

确认：

- Python >= 3.10；否则先安装 3.11/3.12。
- 80 端口由 Nginx 监听。
- 22、80 端口在云安全组中放行。

建议首次登录后写入自己的 SSH 公钥，后续不再使用密码：

```bash
mkdir -p /root/.ssh
chmod 700 /root/.ssh
printf '%s\n' 'ssh-ed25519 AAAA...' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

## 2. 修改 hostname

```bash
hostnamectl set-hostname xiaojunyang
grep -q '^127\.0\.1\.1' /etc/hosts \
  && sed -i 's/^127\.0\.1\.1.*/127.0.1.1 xiaojunyang/' /etc/hosts \
  || echo '127.0.1.1 xiaojunyang' >> /etc/hosts
hostnamectl
```

重新登录后提示符应为 `root@xiaojunyang`。如果云主机使用 cloud-init 且重启会重置 hostname，可在 `/etc/cloud/cloud.cfg` 中设置：

```yaml
preserve_hostname: true
```

## 3. 安装依赖

Ubuntu / Debian：

```bash
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx git make
```

RHEL / CentOS / Alibaba Cloud Linux：

```bash
dnf install -y python3 python3-pip nginx git make
```

如果 `python3 --version` 低于 3.10，先安装 Python 3.11/3.12，不要直接使用 Django 5.2。

## 4. 创建用户与目录

```bash
id eduxjy || useradd --system --create-home --home-dir /opt/EduXJY --shell /usr/sbin/nologin eduxjy
cd /opt
git clone https://github.com/<github-username>/EduXJY.git
chown -R eduxjy:eduxjy /opt/EduXJY
```

如果 GitHub 暂时不可访问，可先在本地打包上传，之后再补推仓库：

```bash
# 在本地项目目录
tar --exclude='.venv' --exclude='db.sqlite3' --exclude='media' -czf EduXJY.tar.gz .
scp EduXJY.tar.gz root@121.40.192.55:/tmp/
# 在云主机
mkdir -p /opt/EduXJY && tar -xzf /tmp/EduXJY.tar.gz -C /opt/EduXJY
chown -R eduxjy:eduxjy /opt/EduXJY
```

## 5. 配置 `.env`

```bash
cd /opt/EduXJY
cp deploy/env.production.example .env
chmod 600 .env
```

必须修改：

- `DJANGO_SECRET_KEY`：使用 `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` 生成。
- `DJANGO_ALLOWED_HOSTS=121.40.192.55,xiaojunyang,localhost,127.0.0.1`
- `DJANGO_CSRF_TRUSTED_ORIGINS=http://121.40.192.55`
- `AI_BASE_URL`、`AI_MODEL`、`AI_API_KEY`
- `DEMO_PASSWORD`

不要把 `.env` 提交到 Git，也不要在报告中展示 Key。

## 6. 初始化应用

```bash
cd /opt/EduXJY
sudo -u eduxjy -H make install
sudo -u eduxjy -H .venv/bin/python manage.py migrate
sudo -u eduxjy -H .venv/bin/python manage.py collectstatic --noinput
sudo -u eduxjy -H .venv/bin/python manage.py seed_demo
sudo -u eduxjy -H .venv/bin/python manage.py check --deploy
```

如果已有 `db.sqlite3`，迁移前先备份：

```bash
cp db.sqlite3 "db.sqlite3.bak.$(date +%Y%m%d%H%M%S)"
```

## 7. Gunicorn + systemd

```bash
install -m 644 /opt/EduXJY/deploy/eduxjy.service /etc/systemd/system/eduxjy.service
systemctl daemon-reload
systemctl enable --now eduxjy
systemctl status eduxjy --no-pager
```

服务以 `eduxjy` 用户运行，静态文件权限为 755/644，Nginx 可以直接读取；不需要按发行版修改运行组。

检查只监听本机：

```bash
ss -ltnp | grep 8000
curl -sS http://127.0.0.1:8000/healthz/
```

## 8. Nginx 反向代理

Ubuntu / Debian：

```bash
install -m 644 /opt/EduXJY/deploy/nginx-eduxjy.conf /etc/nginx/sites-available/eduxjy
ln -sfn /etc/nginx/sites-available/eduxjy /etc/nginx/sites-enabled/eduxjy
nginx -t
systemctl reload nginx
```

RHEL 系：

```bash
install -m 644 /opt/EduXJY/deploy/nginx-eduxjy.conf /etc/nginx/conf.d/eduxjy.conf
nginx -t
systemctl reload nginx
```

RHEL 系如 SELinux 为 `Enforcing`：

```bash
setsebool -P httpd_can_network_connect 1
chcon -R -t httpd_sys_content_t /opt/EduXJY/staticfiles
```

`/media/` 在 Nginx 中显式拒绝，避免上传的源文件被公网直接下载；`/static/` 由 Nginx 提供。

## 9. 公网验证

```bash
hostname
systemctl is-active nginx eduxjy
nginx -t
curl -I http://127.0.0.1/healthz/
curl -I http://121.40.192.55/
```

预期：

- `hostname` 输出 `xiaojunyang`。
- `/healthz/` 返回 200 和 `{"status":"ok","database":"ok"}`。
- 根路径返回登录页 200，或 302 跳转到 `/accounts/login/`。
- 浏览器访问 <http://121.40.192.55/> 可看到登录页。

## 10. 截图清单

部署报告应包含：

1. `hostnamectl` 显示 `xiaojunyang`。
2. `nginx -v`、`nginx -t`、`systemctl status nginx`。
3. `systemctl status eduxjy`。
4. `curl -I http://121.40.192.55/`。
5. 浏览器访问公网 IP 的登录页。
6. 登录后的问答页和引用来源。

截图前确认终端中没有密码、API Key、Token。

## 11. 常用运维

```bash
# 查看日志
journalctl -u eduxjy -f
tail -f /var/log/nginx/eduxjy.error.log

# 更新代码
cd /opt/EduXJY
sudo -u eduxjy -H git pull
sudo -u eduxjy -H make install
sudo -u eduxjy -H .venv/bin/python manage.py migrate
sudo -u eduxjy -H .venv/bin/python manage.py collectstatic --noinput
systemctl restart eduxjy

# 备份数据库
cp /opt/EduXJY/db.sqlite3 /root/eduxjy-backup-$(date +%Y%m%d).sqlite3
```

## 12. 安全建议

- 部署完成后更换已经暴露的 root 密码，并优先使用 SSH key。
- 生产环境增加 HTTPS（域名 + Let's Encrypt），并开启 HSTS。
- 不要把 `.env`、`db.sqlite3`、`media/` 放入公开仓库。
- SQLite 适合演示；高并发迁移 PostgreSQL + pgvector。
