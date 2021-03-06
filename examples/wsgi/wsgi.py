from calendar_email_digest import WSGIApplication

application = WSGIApplication(
    wsgi_section='wsgi',
    config_files=['etc/secret.conf']) 

if __name__ == '__main__':
    """Make silly test server. Do not use in production."""
    import sys
    command = sys.argv.pop(1) if len(sys.argv) > 1 else ''
    if command == 'serve':
        port = int(sys.argv.pop(1)) if len(sys.argv) > 1 else 4000
        from wsgiref.simple_server import make_server
        make_server('localhost', port, application).serve_forever()
    elif command in ['-h', '--help']:
        print("Usage: %f serve [port] (default: 4000)" % sys.argv[0])
    elif command:
        raise RuntimeError("Unknown command %r (only known command is 'serve')." % command)
