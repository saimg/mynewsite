# for AMI ami-ab9491df (Ubuntu 12 LTS)


import os
from fabric.contrib import files
from fabric.decorators import task
from fabric.operations import run, open_shell, prompt
from fabric.api import env, local, sudo, put


env.user = "ubuntu"
env.key_filename = "aws-eu-omat.pem"
env.hosts = ["gazetesolfasol.com"]
env.domain = "gazetesolfasol.com"

env.nginx_hosts = ' '.join(env.hosts + [env.domain])

env.git_repo = local('git config --get remote.origin.url', capture=True)
env.project_name = env.git_repo.split('/')[-1].split('.')[0]  # use git file name

env.project_dir = os.path.realpath(os.path.join(os.path.dirname(env.real_fabfile), ".."))
env.server_project_base = '/home/%s' % env.user
env.server_project_dir = os.path.join(env.server_project_base, env.project_name)
env.environment_dir = '%s/env/' % env.server_project_dir
env.warn_only = True

PACKAGES = (
    "libxml2-dev",
    "libxslt1-dev",
    "python-libxml2",
    "python-setuptools",
    "git-core",
    "build-essential",
    
    # PIL
    "python-dev libjpeg-dev libpng-dev zlib1g-dev liblcms1-dev libfreetype6-dev python-imaging",
    
    "uwsgi",
    "uwsgi-plugin-python",
    "nginx-full",
)

def copy_keys():
    run("mkdir -p ~/.ssh/")
    put("~/.ssh/aws_rsa", "~/.ssh/id_rsa", mode=0600)
    put("~/.ssh/aws_rsa.pub", "~/.ssh/id_rsa.pub", mode=0600)
    put("~/.ssh/known_hosts", "~/.ssh/known_hosts", mode=0600)

@task
def deploy():
    run("cd %(server_project_dir)s/; git pull origin master;" % env)
    run("cd %(server_project_dir)s/; source %(environment_dir)sbin/activate; python manage.py migrate;" % env)
    sudo("service uwsgi stop; service uwsgi start", pty=False)
    sudo("service nginx stop; service nginx start", pty=False)

@task
def setup():
    
    # install packages
    sudo("aptitude update")
    sudo("aptitude -y install %s" % (' '.join(PACKAGES),))
    
    # clone repo
    copy_keys()
    run("cd %(server_project_base)s; git clone %(git_repo)s;" % env)
    
    # build environment
    sudo("easy_install virtualenv")
    # use --system-site-packages; pyscopg2 is installed globally
    run("virtualenv --system-site-packages %s" % env.environment_dir)
    run('''source %(environment_dir)sbin/activate;
           pip install -r %(server_project_dir)s/requirements.txt''' % env)
    
    # nginx
    files.upload_template("%(project_dir)s/deploy/nginx/server.conf" % env,
                          "/etc/nginx/nginx.conf", use_sudo=True, context=env)
    sudo("rm -f /etc/nginx/sites-available/default")
    sudo("rm -f /etc/nginx/sites-available/%(project_name)s.conf" % env)
    sudo("rm -f /etc/nginx/sites-enabled/%(project_name)s.conf" % env)
    files.upload_template("%s/deploy/nginx/site.conf" % env.project_dir,
                          "/etc/nginx/sites-available/%(project_name)s.conf" % env,
                          context=env, use_sudo=True)
    sudo('''sudo ln -s /etc/nginx/sites-available/%(project_name)s.conf \
            /etc/nginx/sites-enabled/%(project_name)s.conf''' % env)
    
    # uwsgi
    sudo("rm -f /etc/init/uwsgi.conf")
    files.put("%s/deploy/uwsgi/upstart.conf" % env.project_dir,
              "/etc/init/uwsgi.conf", use_sudo=True)
    
    sudo("rm -f /etc/uwsgi/apps-available/%(project_name)s.ini" % env)
    sudo("rm -f /etc/uwsgi/apps-enabled/%(project_name)s.ini" % env)
    files.upload_template("%(project_dir)s/deploy/uwsgi/app.ini" % env,
                          "/etc/uwsgi/apps-available/%(project_name)s.ini" % env, 
                          use_sudo=True, context=env)
    sudo('''sudo ln -s /etc/uwsgi/apps-available/%(project_name)s.ini \
            /etc/uwsgi/apps-enabled/%(project_name)s.ini''' % env)

    # syncdb
    run("""cd %(server_project_dir)s/;
           source %(environment_dir)sbin/activate; 
           python manage.py syncdb --noinput;""" % env)
    deploy()

@task
def manage():
    prompt(':', 'command')
    run('''cd %(server_project_dir)s/;
           source env/bin/activate;
           python manage.py %(command)s''' % env)

@task
def shell():
    open_shell('''cd %(server_project_dir)s/;
                  source env/bin/activate;
                  python manage.py shell''' % env)
