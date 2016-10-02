#!/usr/bin/env python3 
"""Send email digests of upcoming events from a Google calendar.
"""
import argparse
import configparser
import datetime
import json
import logging
import os
import re
import requests
import sys
    
default_config_file = '/etc/calendar-summary-email.conf'

def loglevel(arg):
    for level in logging._nameToLevel:
        if level.startswith(arg.upper()):
            return level
    raise argparse.ArgumentTypeError('%r does not match any loglevel.' % arg)

def logfile(arg):
    if arg == '-':
        return sys.stderr
    try:
        return open(arg, mode='ab')
    except:
        raise argparse.ArgumentTypeError('Cannot open %r for appending.' % arg)
    
def directory(arg):
    if not os.path.isdir(arg):
        raise argparse.ArgumentTypeError('%r is not a directory.' % arg)
    return arg

configfile_params = (
    (('--config-file', '-c'), dict(
        help="Read additional config file", 
        type=argparse.FileType(mode='r'),
        metavar="FILE",
        action='append')),
    (('--section', '-S'), dict(help="Specify config file section", metavar='NAME')),
    )

params = (
    (('--key', '-k'), dict(help="Google calendar access key.")),
    (('--calendar-id', '-i'), dict(help="Google calendar ID.")),
    (('--subject', '-s'), dict(help="Email subject.")),
    (('--recipient', '-r'), dict(help="Recipient address.", dest='recipient')),
    (('--sender', '-f'), dict(help="Sender address.", dest='sender')),
    )

template_params = (
    (('--html-template', '-b'), dict(help="Template for HTML email.", metavar='FILE', type=open)),
    (('--html-summary', '-z'), dict(help="Template for HTML email event summary.", metavar='FILE', type=open)),
    (('--html-details', '-d'), dict(help="Template for HTML email event details.", metavar='FILE', type=open)),
    (('--plaintext-template', '-B'), dict(help="Template for plaintext email.", metavar='FILE', type=open)),
    (('--plaintext-summary', '-Z'), dict(help="Template for plaintext email event summary.", metavar='FILE', type=open)),
    (('--plaintext-details', '-D'), dict(help="Template for plaintext email event details.", metavar='FILE', type=open)),
    )

optional_params = (
    (('--template-dir', '-t'), dict(
        help="Template dir with {html,plaintext}_{template,details,summary}.tmpl files.", 
        metavar='DIR',
        type=directory)),
    (('--linkprefs', '-l'), dict(
        help="Event link preferences, comma separated, descending priority.",
        default="wikipage, wiki, webpage, website, homepage, site, event, info, more info, more information, googlecalendar")),
    (('--host', '-H'), dict(help="SMTP mail server.", default='localhost')),
    (('--port', '-p'), dict(help="SMTP mail server port.", type=int, default=0)),
    (('--username', '-U'), dict(help="SMTP username.")),
    (('--password', '-P'), dict(help="SMTP password.")),
    (('--outfile', '-o'), dict(help="Save a copy of the generated email.", metavar="FILE", type=argparse.FileType('w'))),
    (('--loglevel', '-L'), dict(
        help="Log events of this severity or worse.", 
        metavar="LEVEL",
        type=loglevel,
        choices=sorted(logging._nameToLevel),
        default='ERROR')),
    (('--logfile', '-F'), dict(
        help="", 
        type=logfile,
        metavar="FILE",
        default=sys.stderr)),
    (('--dryrun', '-R'), dict(help="Do not actually send the email.", action='store_true')),
    (('--help', '-h'), dict(help="Show this help message and exit", action='help')),
    )

def get_url(key, calendar_id):
    template = 'https://www.googleapis.com/calendar/v3/calendars/%(calendar_id)s/events?key=%(key)s&timeMin=%(rfc3339now)s&orderBy=startTime&singleEvents=true'
    return template % dict(
        key=key, 
        calendar_id=calendar_id, 
        rfc3339now=datetime.datetime.utcnow().isoformat()+'Z')

def parse_date(timespec):
    if 'date' in timespec:
        return timespec['date']
    return timespec['dateTime'][:10]

def parse_url(event, linkprefs):
    lines = [l.strip() for l in event.get('description', '').splitlines()]
    for linkpref in linkprefs:
        for line in lines:
            parts = line.split(':', 1)
            if len(parts) > 1 and parts[0].strip().lower() == linkpref:
                m = re.search(r'(https?:\/\/\S+?)(\.?([\s\n]|$))', parts[1])
                if m:
                    return m.group(0)
    return event['htmlLink']

def parse_event(event, linkprefs):
    description = event.get('description', '').strip()
    return dict(
        start = parse_date(event['start']),
        end = parse_date(event['end']),
        title=event['summary'].strip(),
        summary=(description.splitlines() or [''])[0],
        description=description,
        url=parse_url(event, linkprefs))

def get_events(url, linkprefs):
    r = requests.get(url)
    return [parse_event(e, linkprefs) for e in json.loads(r.text)['items']]
    
def datespec(event, sep):
    start = event['start']
    end = event['end']
    if start == end:
        return start
    return start + sep + end 

def html_summary(event, template):
    return template % dict(event, 
        datespec=datespec(event, " &ndash; "))

def html_details(event, index, template):
    description = re.sub(r'(https?:\/\/\S+?)(\.?([\s\n]|$))', r'<a href="\1">\1</a>\2', event['description'], flags=re.I)
    return template % dict(event, 
        index=index,
        datespec=datespec(event, " &ndash; "),
        description=description.replace('\n', '<br>\n'))

def generate_html_email(events, template, summary_template, details_template):
    return template % dict(
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        summary='\n'.join(html_summary(e, summary_template) for e in events),
        details='\n'.join(html_details(e, i + 1, details_template) for i, e in enumerate(events)))

def plaintext_summary(event, index, template):
    return template % dict(event, 
        index=index,
        indent=' ' * (len(str(index)) + 2),
        datespec=datespec(event, " -- "))

def plaintext_details(event, index, template):
    return template % dict(event, 
        index=index,
        datespec=datespec(event, " -- "))


def generate_plaintext_email(events, template, summary_template, details_template):
    return template % dict(
        date=datetime.datetime.now().strftime("%Y-%m-%D"),
        summary='\n'.join(plaintext_summary(e, i + 1, summary_template) for i, e in enumerate(events)),
        details=('\n\n' + '-'*75 + '\n\n').join(plaintext_details(e, i + 1, details_template) for i, e in enumerate(events)))

def compose_email(sender, recipient, subject, html, plaintext):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.attach(MIMEText(plaintext, 'plain', "utf-8"))
    msg.attach(MIMEText(html, 'html', "utf-8"))
    return msg

def send_email(msg, smtp_server='localhost', smtp_port=0, smtp_username=None, smtp_password=None):
    
    import smtplib
    
    s = smtplib.SMTP(smtp_server, smtp_port)
    if smtp_username:        
        s.login(smtp_username, smtp_password)
    s.sendmail(msg['From'], msg['To'], msg.as_string())
    s.quit()

def add_arguments(parser, argspecs):
    for names, specs in argspecs:
        parser.add_argument(*names, **specs)

def get_config(argv):
    def attrname(argname):
        return argname.strip('-').replace('-', '_')
    
    conf_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False
        )
    add_arguments(conf_parser.add_argument_group('configfile options'), configfile_params)
    config, remaining_argv = conf_parser.parse_known_args()
    config_files = config.config_file
    section = config.section
    required_group = conf_parser.add_argument_group('required')
    add_arguments(required_group, params)
    add_arguments(required_group, template_params)
    add_arguments(conf_parser.add_argument_group('optional'), optional_params)

    defaults = dict()
    if os.path.isfile(default_config_file):
        config_files.insert(0, default_config_file)
    if config_files:
        if not section:
            conf_parser.error('Section not specified.')
        cfp = configparser.ConfigParser()
        cfp.read(f.name for f in config_files)
        defaults = {attrname(k):v for k, v in cfp.items(section)}

    argparser = argparse.ArgumentParser(parents=[conf_parser], description=__doc__, add_help=False)
    argparser.set_defaults(**defaults)
    config = argparser.parse_args(remaining_argv)
    config.linkprefs = [s.strip() for s in config.linkprefs.split(',')]
    
    for argnames, _ in params:
        if not getattr(config, attrname(argnames[0])):
            argparser.error("%s/%s not specified." % argnames)
            
    for (long, _), _ in template_params:
        attr = attrname(long)
        if getattr(config, attr):
            continue
        if not os.path.isdir(config.template_dir):
            argparser.error("%s template not specified." % long)
        try:
            f = open(os.path.join(config.template_dir, attr + '.tmpl'))
        except:
            raise
            argparser.error("%s template not specified, and no %s.tmpl present in template_dir %r." % (long, attr, config.template_dir))
        setattr(config, attr, f)

    def pluralize(name, items, plural=None):
        if plural is None:
            plural = name + 's'
        if len(items) == 1:
            return name + " " + str(items[0])
        return "%s %s and %s" % (name, ', '.join(str(it) for it in items[:-1]), items[-1]) 
        
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', stream=config.logfile, level=getattr(logging, config.loglevel))
    logging.debug('Loglevel set to %s.', config.loglevel)
    logging.info('Program start, config OK.')
    if config_files:
        logging.debug('Read section %r in %s.', section, pluralize('config file', [f.name for f in config_files]))

    return config

def main(argv=None):
    if argv is None:
        argv = sys.argv
    config = get_config(argv)
    url = get_url(config.key, config.calendar_id)
    logging.debug("API url %r.", url)
    events = get_events(url, config.linkprefs)
    if not events:
        logging.info('No events to report, aborting.')
        return 0
    logging.info("Found %s events", len(events))
    logging.debug("Generating HTML message.")
    html = generate_html_email(
        events, config.html_template.read(), config.html_summary.read(), config.html_details.read())
    logging.debug("Generating plaintext message.")
    plaintext = generate_plaintext_email(
        events, config.plaintext_template.read(), config.plaintext_summary.read(), config.plaintext_details.read())
    logging.debug("Composing multipart email.")
    msg = compose_email(config.sender, config.recipient, config.subject, html, plaintext)
    if config.outfile:
        logging.debug("Saving email copy to %s.", config.outfile.name)
        config.outfile.write(msg.as_string())
    if config.dryrun:
        logging.info("Dry run requested, not sending email.")
        return 0
    logging.debug("Sending email.")
    send_email(msg, config.host, config.port, config.username, config.password)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(int(main()))
    except SystemExit:
        raise
    except:
        from traceback import format_exc
        logging.fatal(format_exc())
        raise