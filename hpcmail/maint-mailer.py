#!/usr/bin/env python

import argparse
import datetime
import os
import socket
import sys
import email.message
import email.utils
import smtplib

sd = os.path.dirname(os.path.realpath(__file__)) + '/'

argp = argparse.ArgumentParser(prog='maint-mailer', description="Send out emails for maintenance")
argp.add_argument('-l', '--list', action='store_true', help="Generate formatted recipients string only. Don't email or create message")
argp.add_argument('-n', '--dry-run', action='store_true', help="Don't actually email anyone, just serialize message objects to stdout")
argp.add_argument('-i', '--individual', action='store_true', help="Send individual per-user messsages instead of one large bcc.")
argp.add_argument('-p', '--processes', action='store_true', help="Send info about open sessions and currently running processes. Requires -i")
argp.add_argument('-m', '--multiple', action='store_true', help="Send the notice to all of each user's emails in CSV instead of just one")
argp.add_argument('-r', '--regular', action='store_true', help="Convenience option for hosts that are scheduled for regular reboots. Automatically sets --individual, --processes, --subject, and generates an email message from template.")
argp.add_argument('-s', '--sender', metavar='SENDER', default='admin@hpc.site', help="Provide a From address [admin@hpc.site]")
argp.add_argument('-c', '--cc', metavar='CC', default='admin@hpc.site', help="Provide an address to cc [admin@hpc.site]")
argp.add_argument('-H', '--host', metavar='PROCHOST', default=socket.gethostname(), help="Choose a remote host to check processes on [localhost]")
argp.add_argument('-I', '--identity', metavar='SSHID', help="Choose an SSH identity file to use for connection to PROCHOST")
argp.add_argument('--rpy', default="/usr/bin/python3", help="Remote python interpreter to use to gather procs over ssh")
argp.add_argument('-S', '--smtp', metavar='MAILHOST', default='smtp-relay.gmail.com', help="Provide the SMTP relay host [smtp-relay.gmail.com]")
argp.add_argument('-C', '--csv-file', metavar='CSV', type=argparse.FileType('r'), default=sd+'users.csv', help="Provide the CSV file to load users from [users.csv]")
argp.add_argument('-t', '--subject', metavar='SUBJECT', help="Optionally provide a subject for the email message")
argp.add_argument('-F', '--message-file', metavar='MESSAGE', default=sd+'maint.txt', help="Provide a plain text file with the message to send [files/maint.txt]")
argp.add_argument('-J', '--message-template', metavar='MESSAGE', default=sd+'maint.j2', help="Provide a Jinja2 template file with the message to send [files/maint.j2]")
argp.add_argument('users', nargs='*', metavar='USERS', help="List of users to send email to. If omitted, defaults to all users on localhost except for the owner of the process running this script")
args = argp.parse_args()

# convenient automation for regular scheduled reboots
if args.regular:
    hostname = args.host
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%m/%d")
    try:
        import jinja2
        tl = jinja2.FileSystemLoader(searchpath="/")
        te = jinja2.Environment(loader=tl)
        tf = args.message_template
        tm = te.get_template(tf)
        rm = tm.render(hostname=hostname, tomorrow=tomorrow)
    except ImportError:
        argp.error("cannot use --regular without jinja2")
    args.subject = f"{hostname} reboot tomorrow {tomorrow} 8AM US Eastern time"
    args.individual = True
    args.processes = True

users = load_users(args.csv_file)
smtp = None if (args.dry_run or args.list) else smtplib.SMTP(args.smtp)

if args.processes and not args.individual:
    argp.error("--processes also requires --individual")

if args.individual and args.list:
    argp.error("cannot use both --individual and --list")

if (not len(args.users) or (args.processes)) and args.host == socket.gethostname():
    import proc
    procs = proc.get_host_procs()

elif args.host != socket.gethostname():
    import paramiko
    import proc
    from proc import proc_t
    if not args.identity:
        print("WARNING: no SSH identity file supplied. Will use priority:",
              "1) any keys found through SSH agent",
              "2) any generic keys (~/.ssh/(id_rsa|id_dsa|id_ecdsa)")

    sftp_path = '/tmp/proc.py'
    gather_procs_cmdline = [args.rpy, sftp_path]

    client = paramiko.client.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.client.WarningPolicy)
    client.connect(args.host, key_filename=args.identity)
    
    sftp = client.open_sftp()
    sftp.put(sd+'proc.py', sftp_path)
    sftp.close()
    
    stdin, stdout, stderr = client.exec_command(" ".join(gather_procs_cmdline))
    procs = proc.deserialize_host_procs(stdout.read())
    client.close()

def get_user(v, k):
    """get user object matching provided key"""
    for u in users:
        if getattr(u, k) == v:
            return u

def get_mail(u):
    """get first found or all emails"""
    addrs = u.mail
    if args.multiple:
        return addrs
    for addr in addrs:
        if addr.endswith('@hpc.site'):
            return [addr]
    return [addrs[0]]

def message_string():
    """retrieve the message string"""
    if args.regular: return f"{rm}\n"
    with open(args.message_file, 'r') as mf:
        m = mf.read()
    return m

def mail_user(m, addendum):
    """create a mail object and mail user"""
    msg = email.message.Message()
    msg['From'] = args.sender
    msg['Cc'] = args.cc
    if args.individual:
        msg['To'] = m
    else:
        msg['Bcc'] = m
    if args.subject:
        msg['Subject'] = args.subject

    msg.set_payload(message_string() + addendum)
    
    if args.dry_run:
        print(msg)
    else:
      smtp.send_message(msg, from_addr = args.sender, to_addrs = None)

def targets():
    """get target users based on psutil processes or custom command line input"""
    if len(args.users):
        return args.users
    return set(p.username for p in procs if (p.username != os.getlogin() and p.username in set(u.name for u in users)))

def get_user_processes(name):
    """get list of pids for each user"""
    return [p for p in procs if p.username == name]

recipients = targets()

if not args.individual:
    addrs = []
    for user in recipients:
        u = get_user(user, 'name')
        addrs.append(', '.join((email.utils.formataddr((u.fullname, a)) for a in get_mail(u))))

    if args.list:
        print(', '.join(addrs))
    else:
        mail_user(', '.join(addrs), '')

else:
    for user in recipients:
        u = get_user(user, 'name')
        try:
            addrs = (email.utils.formataddr((u.fullname, a)) for a in get_mail(u))
        except:
            continue
        addendum = ''

        if args.processes:
            uprocesses = get_user_processes(u.name)
            addendum += "\nYou currently own the following processes:\n\n"
            for p in uprocesses:
                addendum += "\tPID {} - {}\n".format(p.pid, ' '.join(p.cmdline[:50]))

        mail_user(', '.join(addrs), addendum)
        if not args.dry_run:
            print("Mailed user {}".format(u.fullname))
