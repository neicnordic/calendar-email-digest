# calendar-email-digest
Send email digests of upcoming events from a Google calendar.

## Prerequisites

1. Python 2
2. Requests module (eg `$ pip install requests`, or `yum install python-requests`).
3. A server access key to a google calendar, configured to be usable from the IP address where this program will run.

## Usage

```
$ python src/calendar-email-digest.py -h
usage: calendar_email_digest.py [--config-file FILE] [--section NAME]
                                [--key KEY] [--calendar-id CALENDAR_ID]
                                [--subject SUBJECT] [--recipient RECIPIENT]
                                [--sender SENDER] [--html-template FILE]
                                [--html-summary FILE] [--html-details FILE]
                                [--plaintext-template FILE]
                                [--plaintext-summary FILE]
                                [--plaintext-details FILE]
                                [--template-dir DIR] [--linkprefs LINKPREFS]
                                [--host HOST] [--port PORT]
                                [--username USERNAME] [--password PASSWORD]
                                [--textfile FILE] [--htmlfile FILE]
                                [--emailfile FILE] [--loglevel LEVEL]
                                [--logfile FILE] [--no-send] [--help]

Send email digests of upcoming events from a Google calendar.

configfile options:
  --config-file FILE, -c FILE
                        Read additional config file
  --section NAME, -s NAME
                        Specify config file section

required:
  --key KEY, -k KEY     Google calendar access key. Must be enabled for this
                        machine's IP address.
  --calendar-id CALENDAR_ID, -i CALENDAR_ID
                        Google calendar ID.
  --subject SUBJECT, -S SUBJECT
                        Email subject.
  --recipient RECIPIENT, -r RECIPIENT
                        Recipient address.
  --sender SENDER, -f SENDER
                        Sender address.
  --html-template FILE, -b FILE
                        Template for HTML email.
  --html-summary FILE, -z FILE
                        Template for HTML email event summary.
  --html-details FILE, -d FILE
                        Template for HTML email event details.
  --plaintext-template FILE, -B FILE
                        Template for plaintext email.
  --plaintext-summary FILE, -Z FILE
                        Template for plaintext email event summary.
  --plaintext-details FILE, -D FILE
                        Template for plaintext email event details.

optional:
  --template-dir DIR, -t DIR
                        Template dir with
                        {html,plaintext}_{template,details,summary}.tmpl
                        files.
  --linkprefs LINKPREFS, -l LINKPREFS
                        Event link preferences, comma separated, descending
                        priority.
  --host HOST, -H HOST  SMTP mail server.
  --port PORT, -p PORT  SMTP mail server port.
  --username USERNAME, -U USERNAME
                        SMTP username.
  --password PASSWORD, -P PASSWORD
                        SMTP password.
  --textfile FILE, -T FILE
                        Save a copy of the generated plaintext message.
  --htmlfile FILE, -O FILE
                        Save a copy of the generated html message.
  --emailfile FILE, -E FILE
                        Save a copy of the generated email.
  --loglevel LEVEL, -L LEVEL
                        Log events of this severity or worse.
  --logfile FILE, -F FILE
  --no-send, -N         Do not actually send the email.
  --help, -h            Show this help message and exit
  ```

## Configuration

Reads .ini style configfile from `/etc/calendar-email-digest.conf` (if exists). Use `--config-file /path/to/secret.conf` on command line to read additional config file(s). This is useful for example for separating access keys and passwords from general config. 

See [examples/etc/example.conf](examples/etc/example.conf) for an example configuration.

## Email templates

Recommended: put template files in a directory and name them

* html_template.templ
* html_summary.templ
* html_details.templ
* plaintext_template.templ
* plaintext_summary.templ
* plaintext_details.templ

and then point to this directory with `--template-dir /path/to/dir` in configuration. Override individual templates if you like with eg `--html-template /path/to/file` or `--plaintext-summary /path/to/file`.

See the [examples/templ/](examples/templ/) directory for examples.
