#!/usr/bin/env python
"""Send email digests of upcoming events from a Google calendar.
"""
import argparse
import ConfigParser
import datetime
import json
import logging
import os
import re
import requests
import sys

default_config_file = '/etc/calendar-email-digest.conf'

loglevels = [name for val, name in sorted(logging._levelNames.items()) if isinstance(name, str)]

def loglevel(arg):
    for level in logging._levelNames:
        if isinstance(level, str) and level.startswith(arg.upper()):
            return level
    raise argparse.ArgumentTypeError('%r does not match any loglevel.' % arg)

def logfile(arg):
    if arg == '-':
        return sys.stderr
    try:
        return open(arg, mode='a')
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
    (('--section', '-s'), dict(help="Specify config file section", metavar='NAME')),
    )

params = (
    (('--key', '-k'), dict(help="Google calendar access key. Must be enabled for this machine's IP address.")),
    (('--calendar-id', '-i'), dict(help="Google calendar ID.")),
    (('--subject', '-S'), dict(help="Email subject.")),
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
    (('--textfile', '-T'), dict(help="Save a copy of the generated plaintext message.", metavar="FILE", type=argparse.FileType('w'))),
    (('--htmlfile', '-O'), dict(help="Save a copy of the generated html message.", metavar="FILE", type=argparse.FileType('w'))),
    (('--emailfile', '-E'), dict(help="Save a copy of the generated email.", metavar="FILE", type=argparse.FileType('w'))),
    (('--loglevel', '-L'), dict(
        help="Log events of this severity or worse.",
        metavar="LEVEL",
        type=loglevel,
        choices=loglevels,
        default='ERROR')),
    (('--logfile', '-F'), dict(
        help="",
        type=logfile,
        metavar="FILE",
        default=sys.stderr)),
    (('--no-send', '-N'), dict(help="Do not actually send the email.", action='store_true')),
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
    description = re.sub(r'([A-Za-z1-9-._]+@[A-Za-z1-9-._]+\.[A-Za-z1-9]+)', r'<a href="mailto:\1">\1</a>', description, flags=re.I)
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
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        summary='\n'.join(plaintext_summary(e, i + 1, summary_template) for i, e in enumerate(events)),
        details=('\n\n' + '-'*75 + '\n\n').join(plaintext_details(e, i + 1, details_template) for i, e in enumerate(events)))

def compose_email(sender, recipient, subject, html, plaintext):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email import utils
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg['Message-ID'] = utils.make_msgid()
    msg['Date'] = utils.formatdate()
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

def _optionxform(optionname):
    """Used by the configfile parsers."""
    return optionname.lower().replace('-', '_')

def get_config(args):
    def attrname(argname):
        return argname.strip('-').replace('-', '_')

    conf_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False
        )
    add_arguments(conf_parser.add_argument_group('configfile options'), configfile_params)
    config, remaining_argv = conf_parser.parse_known_args(args=args)
    config_files = config.config_file or []
    section = config.section
    required_group = conf_parser.add_argument_group('required')
    add_arguments(required_group, params)
    add_arguments(required_group, template_params)
    add_arguments(conf_parser.add_argument_group('optional'), optional_params)

    defaults = dict()
    if os.path.isfile(default_config_file):
        config_files.insert(0, open(default_config_file))
    if config_files:
        if not section:
            conf_parser.error('Section not specified.')
        cfp = ConfigParser.SafeConfigParser()
        cfp.optionxform = _optionxform
        cfp.read(f.name for f in config_files)
        if cfp.has_section(section):
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
            f = open(os.path.join(config.template_dir, attr + '.templ'))
        except:
            argparser.error("%s template not specified, and no %s.templ present in template_dir %r." % (long, attr, config.template_dir))
        setattr(config, attr, f.read())

    return config

def get_events(config):
    url = get_url(config.key, config.calendar_id)
    logging.debug("API url %r.", url)
    text = requests.get(url).text
    raw = json.loads(text)
    if not 'items' in raw:
        logging.fatal('Unexpected response from Google Calendar API:\n' + text)
        raise RuntimeError('Unexpected response from Google Calendar API.')
    return [parse_event(e, config.linkprefs) for e in raw['items']]

def format_events(config, events):
    logging.debug("Generating plaintext message.")
    plaintext = generate_plaintext_email(
        events, config.plaintext_template, config.plaintext_summary, config.plaintext_details)
    logging.debug("Generating HTML message.")
    html = generate_html_email(
        events, config.html_template, config.html_summary, config.html_details)
    logging.debug("Composing multipart email.")
    email = compose_email(config.sender, config.recipient, config.subject, html, plaintext)
    return plaintext, html, email

class WSGIApplication:
    def __init__(self, wsgi_section='wsgi', config_files=None, configs=None):
        self.configs = dict(configs or {})
        self.configs.update(self.get_calendar_configs(wsgi_section, config_files))

    @classmethod
    def get_calendar_configs(cls, wsgi_section, config_files):
        config_files = config_files or []
        if os.path.isfile(default_config_file):
            config_files.insert(0, default_config_file)
        wsgi_config = ConfigParser.SafeConfigParser()
        wsgi_config.optionxform = _optionxform
        wsgi_config.read(config_files)
        def get(option, default=''):
            try:
                return wsgi_config.get(wsgi_section, option)
            except:
                return default
        raw = get('wsgi_calendars')
        if not raw:
            msg = "No wsgi_calendars option in section %r in config files %s"
            raise ValueError(msg % (wsgi_section, config_files))
        wsgi_calendars = [c.strip() for c in raw.split(',')]
        configure_logging(get('logfile', sys.stderr), getattr(logging, get('loglevel', 'info').upper()))
        args = sum((['--config-file', f] for f in config_files), []) + ['--no-send', '-s']
        return {c:get_config(args + [c]) for c in wsgi_calendars}

    def __call__(self, environ, start_response):
        try:
            status, headers, body = self.process_request(environ, start_response)
        except:
            from traceback import format_exc
            logging.error(format_exc())
            status = '500 Internal server error'
            body = self._html_msg(status, 'Please contact the server administrator.').encode('utf-8')
            headers = [('Content-Type', 'text/html; charset=UTF-8')]
        body = body.encode('utf-8')
        headers += [('Content-Length', str(len(body)))]
        start_response(status, headers)
        return [body]

    @classmethod
    def _html_msg(cls, heading, details=''):
        return "<html><head><title>%s</title></head><body><h1>%s</h1>%s</body></html>" % (heading, heading, details)

    def process_request(self, environ, start_response):
        status = '200 OK'
        headers = [('Content-Type', 'text/html; charset=UTF-8')]
        path = environ['PATH_INFO'].lstrip('/')
        if not path:
            ext = ['.txt', '.html', '.eml']
            li = '<li><a href="%s">%s</a></li>'
            cal = '<h2>%s</h2><ul>%s</ul>'
            details = ''.join(cal % (c, ''.join(li % (c+e, c+e) for e in ext)) for c in self.configs)
            body = self._html_msg("Calendar email digest", "<ul>%s</ul>" % details)
            return status, headers, body
        cal, fmt = os.path.splitext(path)
        if cal not in self.configs or not fmt:
            status = '404 Not found'
            body = self._html_msg(status)
            return status, headers, body
        events = get_events(self.configs[cal])
        logging.info("Found %s events", len(events))
        plaintext, html, email = format_events(self.configs[cal], events)
        if fmt == '.html':
            return status, headers, html
        if fmt == '.txt':
            return status, [('Content-Type', 'text/plain; charset=UTF-8')], plaintext
        if fmt == '.eml':
            return status, [('Content-Type', email.get_content_type())], email.as_string()
        raise RuntimeError("Unreachable code reached.")

def configure_logging(stream, level):
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', stream=stream, level=level)

def main(config):
    configure_logging(config.logfile, getattr(logging, config.loglevel))
    logging.info('Program start, config OK.')
    logging.debug('Loglevel set to %s.', config.loglevel)
    events = get_events(config)
    if not events:
        logging.info('No events to report, aborting.')
        return 0
    logging.info("Found %s events", len(events))
    plaintext, html, email = format_events(config, events)
    if config.textfile:
        logging.debug("Saving plaintext copy to %s.", config.textfile.name)
        config.textfile.write(plaintext)
    if config.htmlfile:
        logging.debug("Saving html copy to %s.", config.htmlfile.name)
        config.htmlfile.write(html)
    if config.emailfile:
        logging.debug("Saving email copy to %s.", config.emailfile.name)
        config.emailfile.write(email.as_string())
    if config.no_send:
        logging.info("Dry run requested, not sending email.")
        return 0
    logging.debug("Sending email.")
    send_email(email, config.host, config.port, config.username, config.password)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(int(main(get_config(sys.argv[1:])) or 0))
    except SystemExit:
        raise
    except:
        from traceback import format_exc
        logging.fatal(format_exc())
        raise
