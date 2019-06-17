"""
Routes and views for the flask application.
"""
import subprocess

from datetime import datetime
from flask import Blueprint, request, jsonify, make_response, render_template, url_for, redirect, session

from ldap3 import Server, Connection, ALL, NTLM
from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups as addUsersInGroups

from pyzabbix import ZabbixAPI

ldap_blueprint = Blueprint('ldap', __name__)

session['user'] = request.form['administrator_login'] #domain administrator login
session['password'] = request.form['administrator_password'] #domain administrator password
session['name'] = request.form['server_name'] #hostname 
session['domain'] = request.form['domain_name'] #domain name

session['group'] = request.form['add_group'] #group name for add
session['admin'] = request.form['add_user'] #user name/login for add
admin = session['admin']
session['admin_password'] = request.form['add_password'] #password for user
admin_password = session['admin_password']

session['ip'] = request.form['ip_address_zabbix']

session['php'] = request.form['local_zone']#date.timezone = Europe/Moscow
timezone_php = session['php']

session['zab'] = request.form['local_zone']#php_value date.timezone Europe/Moscow
timezone_zab = session['zab']

session['cos'] = request.form['local_zone']#timedatectl set-timezone Europe/Moscow
timezone_cos = session['cos']

session['date'] = request.form['local_date'] #15 jun 2019 14:14

session['sntp'] = request.form['ntp_server'] #ip address of ntp server
server_ntp = session['sntp']

session['host_name_snmp'] = request.form['name_of_snmp_device']
host_name = session['host_name_snmp']

session['ipsnmp'] = request.form['ip_snmp_device']
ip_address_snmp_device = session['ipsnmp']

#tempid = []
#tempname = []
#temp = {}

def intergration_to_ad():
    #integration in active directory of a CentOS virtual machine
    bashCommand = '/opt/pbis/bin/domainjoin-cli join ' + session['domain'] + ' ' + session['user'] + ' ' + session['password']
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

def add_privileges():
    #enable privileges domain group (session['group'])
    bashCommand = '/opt/pbis/bin/config RequireMembershipOf ' + session['domain'] + '\\Users'
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

def add_user_and_group_to_ad():
    #adding user and group for management zabbix
    server_name = session['name'] + '.' + session['domain']
    connection_user = session['domain'] + '\\' + session['user']

    server = Server(server_name, get_info=ALL)
    connect = Connection(server, user=connection_user, password=session['password'], authentication=NTLM)
    connect.bind()

    #Получение полного доменного имени
    base = server.info.other.get('defaultNamingContext')[0].lower()
    for s in base.split(','):
        if s.starts_with('dc'):
            base_temp.push(s)
    #Преобразование array в string
    dbase = ','.join(base_temp)

    usersDnList = []
    groupsDnList = []

    #DistinguishedName
    user_ou = 'OU=Users,' + dbase
    group_ou = 'OU=Users,' + dbase

    #Создание и добавление группы в active directory
    current_group = 'cn=' + session['group'] + ',' + group_ou
    groupsDnList.append(current_group)
    connect.add(current_group, 'group')

    #Создание и добавление пользователя в active directory
    current_user = 'cn=' + session['admin'] + ',' + user_ou
    usersDnList.append(current_user)
    connect.add(current_user, 'User', 
              {'givenName': session['admin'],
               'sn': session['admin'],
               'userPrincipalName': session['admin'] + '@' + session['domain'], #login@domain.com
               'sAMAccountName': session['admin'], #login
               'userPassword': session['admin_password']}) #password
    #Функция добавляющая списки пользователей в списки групп 
    add_to_ad = addUsersInGroups(connect, usersDnList, groupsDnList)
    
    return add_to_ad

def add_user_to_zabbix():
    
    USER_FROM_ZABBIX = {
        #Имя пользователя zabbix. Оно точно такое же 
        #как и у пользователя, которого мы добавляем 
        #в active directory
        'alias':f'{admin}',
        #Пароль пользователя, который он будет использовать
        #для аутентификации через ldap под учетной записью
        #пользователя домена
        'passwd':f'{admin_password}',
        #Группа Zabbix superadmins
        'usrgrps': [ 
            {
                'usrgrpid': '7'
                } 
            ]
        }
    
    #Подключение к zabbix серверу, используя
    #default account zabbix superadmin
    zabbix = ZabbixAPI('http://' + session['ip'] + '/zabbix', user='Admin', password='zabbix')
    
    #Сомневаюсь, что это работает так
    #zabbix_users = zabbix.user.create()

    #Делаем запрос к zabbix серверу,
    #указывая метод, который хотим использовать
    #и параметры для передачи их в метод
    zabbix_users = zabbix.do_request('user.create', USER_FROM_ZABBIX)

    return zabbix_users

#Абсолютно бесполезная херня в том случае, если
#все же откажусь от добавления пользователем шаблонов
#def get_templates_for_snmp():
#    #Подключение к zabbix серверу, используя
#    #default account zabbix superadmin
#    zabbix = ZabbixAPI('http://' + session['ip'] + '/zabbix', user='Admin', password='zabbix')
#    #Получаем массив шаблонов содержащихся в группе хостов Network Devices
#    #и выводим их id и полное имя шаблона
#    templates = zabbix.template.get(groupids=9, output=['itemid','name'])
#    #Проходимся по массиву шаблонов, помещая каждый экземпляр в словарь
#    #Где key:id, а value:name и попутно разделяем их на два разных списка
#    #Для упрощения поиска нужного шаблона
#    for template in templates:
#        temp[template['templateid']] = template['name']
#        tempid.append(template['templateid'])
#        tempname.append(template['name'])
#    return template['templateid'], template['name']

#Тест. Добавление узла сети с пользовательскими параметрами.
def add_host_with_snmp_interface():
    
    HOST_FROM_ZABBIX = {
    #Имя добавляемого узла сети
    "host":f'{host_name}',
    "interfaces": [
            {
                #SNMP interface
                "type": 2,
                #Указание основного адреса ip или dns
                "main": 1,
                #Использование ip вместо dns
                "useip": 1,
                "ip":f'{ip_address_snmp_device}',
                "dns": "",
                "port": "10050"
            }
        ],
        "groups": [
            {
                #Host Group специально для устройств
                #с интерфейсами поддерживающими snmp
                "groupid": "17"
            }
        ],
        #Добавление ссылок на темплейты (в данном случае указывается id темплейта)
        "templates": [
            {
                "templateid": "10280"
            },
            {
                "templateid": "10208"
            },
        ]
}
    #Подключение к zabbix серверу, используя
    #default account zabbix superadmin
    zabbix = ZabbixAPI('http://' + session['ip'] + '/zabbix', user='Admin', password='zabbix')

    req = zabbix.do_request('host.create',HOST_FROM_ZABBIX)
    return req

#Setup timezone
def setup_timezone_php():
    bashCommand = f'sed -i "878s%.*%date.timezone = {timezone_php}%g" /etc/php.ini'
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

def setup_timezone_zabbix():
    bashCommand = f'sed -i "20s%.*%        php_value date.timezone {timezone_zab}%g" /etc/httpd/conf.d/zabbix.conf'
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

def setup_timezon_centos():
    bashCommand = f'timedatectl set-timezone {timezone_cos}'
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

def setup_local_time():
    bashCommand = 'hwclock --set --date ' + session['date']
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

def setup_ntp():
    bashCommand = f'ntpdate -u {server_ntp}'
    output = subprocess.check_output(['bash','-c', bashCommand])
    return output

#@app.route('/')
#@app.route('/conntoad')
#def conntoad():
#    """Renders the home page."""
#    return render_template(
#        'conntoad.html',
#        title='connection',
#        year=datetime.now().year,
#    )

#@app.route('/addadmin')
#def addadmin():
#    """Renders the home page."""
#    return render_template(
#        'addadmin.html',
#        title='adding',
#        year=datetime.now().year,
#    )

#@app.route('/setupntp')
#def setupntp():
#    """Renders the home page."""
#    return render_template(
#        'setupntp.html',
#        title='setup ntp',
#        year=datetime.now().year,
#    )

#@app.route('/snmpdevices')
#def snmpdevices():
#    """Renders the home page."""
#    return render_template(
#        'snmpdevices.html',
#        title='snmp devices',
#        year=datetime.now().year,
#    )

#@app.route('/info')
#def info():
#    """Renders the home page."""
#    return render_template(
#        'info.html',
#        title='info',
#        year=datetime.now().year,
#    )
