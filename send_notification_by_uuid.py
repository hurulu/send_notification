#!/usr/bin/env python

import sys,string
import os
import re
import MySQLdb as mdb
import smtplib
import time
from email.mime.text import MIMEText
from keystoneclient.exceptions import AuthorizationFailure
from keystoneclient.v2_0 import client as ks_client
from novaclient.v1_1 import client as nova_client


def get_instance_uuid():
    results = []
    fp = open(uuid_file,"r")
    for line in fp.readlines():
    	results.append(line.rstrip('\n'))
    fp.close()
    return results

#print compute_list
def get_keystone_client():

    auth_username = os.environ.get('OS_USERNAME')
    auth_password = os.environ.get('OS_PASSWORD')
    auth_tenant = os.environ.get('OS_TENANT_NAME')
    auth_url = os.environ.get('OS_AUTH_URL')

    try:
        return ks_client.Client(username=auth_username,
                                password=auth_password,
                                tenant_name=auth_tenant,
                                auth_url=auth_url)
    except AuthorizationFailure as e:
        print e
        print 'Authorization failed, have you sourced your openrc?'
        sys.exit(1)


def get_nova_client():

    auth_username = os.environ.get('OS_USERNAME')
    auth_password = os.environ.get('OS_PASSWORD')
    auth_tenant = os.environ.get('OS_TENANT_NAME')
    auth_url = os.environ.get('OS_AUTH_URL')

    nc = nova_client.Client(auth_username,
                            auth_password,
                            auth_tenant,
                            auth_url,
                            service_type='compute')
    return nc

def get_tenant_dict(client):
    result_list = {}
    for tenant in client.tenants.list():
	result_list[tenant.__dict__['id']] = tenant.__dict__['name']
    return result_list
	
def get_user_dict(client):
    result_list = {}
    for user in client.users.list():
	result_list[user.__dict__['id']] = user.__dict__['name']
    return result_list

def get_data():
    db_host = os.environ.get("NOVA_DB_HOST")
    db_user = os.environ.get("NOVA_DB_USER")
    db_pass = os.environ.get("NOVA_DB_PASS")
    db_name = os.environ.get("NOVA_DB_NAME")
    results = []
    try:
        con = mdb.connect(db_host, db_user, db_pass, db_name);
        cur = con.cursor()
        for instance_uuid in instance_uuids:
        	cur.execute("select uuid,user_id,project_id,address,hostname from instances join fixed_ips on instances.uuid=%s and fixed_ips.instance_uuid=%s and instances.deleted=0 and fixed_ips.deleted=0",(instance_uuid,instance_uuid))
    		result = cur.fetchone()
    		if result:
        		results.append(result)
        
    except mdb.Error, e:
      
        print "Error %d: %s" % (e.args[0],e.args[1])
        sys.exit(1)
        
    finally:    
            
        #if con:    
        #    con.close()
	return results

def generate_affecting_instance():
	results = {}
	for record in data:
		instance_uuid = record[0]
		user_id = record[1]
		tenant_id = record[2]
		instance_ip = record[3]
		instance_name = record[4]
		user_email = user_list_dict[user_id]
		tenant_name = tenant_list_dict[tenant_id]
		if not results.has_key(user_email):
			results[user_email] = []
		affected_instances = [instance_uuid,instance_ip,instance_name,tenant_name]
		results[user_email].append(affected_instances)
	return results

def sendMail(subject,to_email,content):
	mail_host = '127.0.0.1'
	fp = open(head, 'rb')
	msg1 = fp.read()
	fp.close()
	msg1 += "%-40s\t%-20s\t%-44s\t%-32s\n" % ("UUID", "IP ADDRESS", "Host", "Project")
	for i in content:
		msg1 += "%-40s\t%-20s\t%-44s\t%-32s\n" % (str(i[0]), str(i[1]), str(i[2]), str(i[3]))


	fp = open(tail,'rb')
	msg2 = fp.read()
	fp.close()

	cc_msg = MIMEText( to_email + "\n" + msg1 + msg2,'plain','utf-8')
	cc_msg.add_header('Reply-To','support@rc.nectar.org.au')
	cc_msg.add_header('From','support@rc.nectar.org.au')
	cc_msg['Subject'] = subject

	msg = MIMEText( msg1 + msg2,'plain','utf-8' )
	msg.add_header('Reply-To','support@rc.nectar.org.au')
	msg.add_header('From','support@rc.nectar.org.au')
	msg['Subject'] = subject

	try:
	    s = smtplib.SMTP()
	    s.connect(mail_host)
	    #send mail
	    #print to_email
	    if len(sys.argv) == 3 and sys.argv[2] == 'SEND':
	    	s.sendmail('no-reply@rc.nectar.org.au',to_email,msg.as_string())
	    else:
	    	s.sendmail('no-reply@rc.nectar.org.au',test_email,cc_msg.as_string())
	    s.quit()
	except Exception ,e:
	    print e

if __name__ == '__main__':
	#Main
	conf_dir = sys.argv[1]
	uuid_file = conf_dir + "/uuid"
	head = conf_dir + "/head"
	tail = conf_dir + "/tail"
	log_file = conf_dir + "/log"
	test_email = "lei.zhang@ersa.edu.au"
	subject = '[NeCTAR eRSA Node Notification] A scheduled upgrade on 12/03/2015 will affect your instances'
	email_pattern = re.compile('([\w\-\.\']+@(\w[\w\-]+\.)+[\w\-]+)')
	kc = get_keystone_client()
	instance_uuids = get_instance_uuid()
	data = get_data()
	tenant_list_dict = get_tenant_dict(kc)
	user_list_dict = get_user_dict(kc)
	email_data = generate_affecting_instance()

	fp = open(log_file,"w")
	for email in email_data.keys():
		if email_pattern.match(email) is None:
			print ("ERROR : %s is not a valid email address!" % email)
		print ("%s => %s , %s instances affected" % (email,email_data[email],len(email_data[email])))
		time_string = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
		fp.write("%s : %s => %s , %s instances affected \n" % (time_string,email,email_data[email],len(email_data[email])))
		sendMail(subject,email,email_data[email])
		time.sleep(2)
	fp.close()
