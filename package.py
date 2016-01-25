#!/usr/bin/python
# -*- coding: utf-8 -*-
# author:   Jan Hybs

import sys, os, platform, re, urllib, tarfile, shutil, time
from subprocess import Popen, PIPE
from optparse import OptionParser

quited = False


class Command(object):
    LS = 'ls'
    LS_CWD = 'ls {cwd}'
    ECHO_SYSTEM = 'echo {system}'


def get_system_simple():
    return re.match(r'([a-zA-Z]+)', platform.system().strip().lower()).group(1)


def get_x64():
    return '64' if sys.maxsize > 2 ** 32 else '32'


def mkdirr(location):
    location = os.path.abspath(location)
    folders = re.split(r'[/\\]+', location)
    for i in range(2, len(folders) + 1):
        folder = os.path.sep.join(folders[0:i])
        if os.path.exists(folder):
            continue

        os.mkdir(folder, 0777)


def padding(s='', pad='\n        ', tail=10):
    if s is None or not s.strip():
        return ''
    lines = s.strip().splitlines()
    if len(lines) > tail:
        return pad + '...' + pad + pad.join(lines[-tail:])
    return pad + pad.join(lines)


default_kwargs = dict(
    cwd=os.getcwd(),
    x64=get_x64(),
    system=platform.system(),
    system_simply=get_system_simple(),
    system_sigs={
        'linux': { '32': None, '64': 'linux_x86_64' },
        'windows': { '32': 'windows_x86_32', '64': 'windows_x86_64' },
        'cygwin': { '32': None, '64': None }
    }
)


def fix_args(plat=None, x64=None, ext=None):
    plat = plat or get_system_simple()
    x64 = x64 or get_x64()
    ext = ext or { 'linux': '.tar.gz', 'windows': '.exe' }.get(plat)
    folder = default_kwargs['system_sigs'].get(plat).get(x64)
    location = os.path.join(folder, folder + ext)
    mkdirr(os.path.dirname(location))

    return plat, x64, ext, folder, location


def find_flow_bin(plat=None, x64=None, ext=None, **kwargs):
    plat, x64, ext, folder, location = fix_args(plat, x64, ext)
    if plat == 'linux':
        files = os.listdir(folder)
        for f in files:
            if f.lower().find('flow123d') >= 0 and os.path.isdir(os.path.join(folder, f)):
                return os.path.join(folder, f, 'bin', 'flow123d')

    if plat == 'windows':
        return os.path.join(folder, 'bin', 'flow123d.exe')
    return None


def run_command(cmd, **kwargs):
    full_kwargs = default_kwargs.copy()
    full_kwargs.update(kwargs)

    if type(cmd) is list:
        full_cmd = cmd
        shell = False
    else:
        full_cmd = [cmd.format(**full_kwargs)]
        shell = True
    print "Running: {full_cmd}".format(full_cmd=str(full_cmd))

    process = Popen(full_cmd, stdout=PIPE, stderr=PIPE, shell=shell)
    stdout, stderr = process.communicate()

    return process, stdout, stderr


def check_error(process, stdout, stderr):
    stderr = "" if not stderr else stderr
    stdout = "" if not stdout else stdout

    if process.returncode != 0:
        if not quited:
            print 'Non-zero exit! (exited with {code})'.format(code=process.returncode)
            if stderr.split():
                print 'Stderr: {stderr}'.format(stderr=padding(stderr.strip()))
            if stdout.split():
                print 'Stdout: {stdout}'.format(stdout=padding(stdout.strip()))
        return process.returncode

    print 'Execution successful!'
    if not quited:
        if stderr.split():
            print 'Stderr: {stderr}'.format(stderr=padding(stderr.strip()))
        if stdout.split():
            print 'Stdout: {stdout}'.format(stdout=padding(stdout.strip()))
    return 0


def action_download_package(server='http://flow.nti.tul.cz/packages', version='0.0.master',
                            plat=None, x64=None, ext=None, **kwargs):
    plat, x64, ext, folder, location = fix_args(plat, x64, ext)

    fmt_object = dict(
        server=server,
        version=version,
        filename=folder + ext,
        ext=ext,
        x64=x64,
        plat=plat
    )

    download_url = "{server}/{version}/flow123d_{version}_{filename}".format(**fmt_object)
    #download_url = "http://bacula.nti.tul.cz/~jan.hybs/public/public_html/Flow123d-1.8.JHy_embedded_python-Linux.tar.gz"

    print 'Downloading file {file}'.format(file=download_url)
    filename, headers = urllib.urlretrieve(download_url, location)
    if not quited:
        print 'Downloaded', filename, padding(str(headers))
    return 0


def action_install(plat=None, x64=None, ext=None, **kwargs):
    plat, x64, ext, folder, location = fix_args(plat, x64, ext)

    if plat == 'linux':
        print 'Extracting: {file}'.format(file=location)
        tar_file = tarfile.open(location, 'r:gz')
        tar_file.extractall(folder)
        print 'Extracting done'
        return 0

    if plat == 'windows':
        installer_location = os.path.abspath(location)
        command = [
            installer_location,
            '/S', '/NCRC',
            '/D=' + os.path.abspath(folder)
        ]
        print 'Installing...'
        process, stdout, stderr = run_command(command)
        check_error(process, stdout, stderr)
        if process.returncode != 0:
            return process.returncode
        print 'Installing done'
        return 0


def action_run_flow(plat=None, x64=None, ext=None, **kwargs):
    plat, x64, ext, folder, location = fix_args(plat, x64, ext)
    flow_loc = find_flow_bin(plat=None, x64=None, ext=None, **kwargs)

    # cross-platform run
    if not flow_loc:
        print 'Could not find flow123d binary location'
        return 1

    process, stdout, stderr = run_command([flow_loc, ' --version'])

    # check output to determine success or failure
    check_error(process, stdout, stderr)
    out = stderr + stdout
    if out.find('This is Flow123d') >= 0:
        print 'String "{s}" found'.format(s='This is Flow123d')
        return 0
    print 'String "{s}" not found in output'.format(s='This is Flow123d')
    return 1


def action_python_test(plat=None, x64=None, ext=None, **kwargs):
    plat, x64, ext, folder, location = fix_args(plat, x64, ext)
    flow_loc = find_flow_bin(plat=None, x64=None, ext=None, **kwargs)
    root = os.path.split(os.path.split(flow_loc)[0])[0]
    test_loc = os.path.join(root, 'tests', '03_transport_small_12d', 'flow_implicit.con')
    output_loc = os.path.join(root, 'output')

    command = [flow_loc, '-s', test_loc, '-o', output_loc]
    process, stdout, stderr = run_command(command)
    check_error(process, stdout, stderr)
    if process.returncode != 0:
        return process.returncode

    out = stderr + stdout
    match = re.match(r'.*(profiler_info_[0-9_\.-]+\.log\.json\.txt file generated).*', out.replace('\n', ' '))
    if not match:
        print 'Could not find message about generating json file!'
        return 1
    print 'String "{msg}" found'.format(msg=match.group(1))
    return 0


def action_uninstall(plat=None, x64=None, ext=None, **kwargs):
    plat, x64, ext, folder, location = fix_args(plat, x64, ext)

    print 'Uninstalling flow123d...'

    if plat == 'linux':
        # only remove install folder
        pass

    if plat == 'windows':
        uninstaller_location = os.path.abspath(os.path.join(folder, 'Uninstall.exe'))
        command = [uninstaller_location, '/S']
        process, stdout, stderr = run_command(command)
        check_error(process, stdout, stderr)
        if process.returncode != 0:
            return process.returncode

    # add sleep since windows spawns child which is not bound by parent
    # so exiting parent does not exit children as well
    time.sleep(5)

    shutil.rmtree(os.path.abspath(folder), True)
    shutil.rmtree(os.path.abspath('output'), True)
    if os.path.exists(folder):
        print 'Uninstallation not successful!'
        print os.listdir(folder)
        return 1

    print 'Uninstallation successful!'
    return 0


parser = OptionParser()
parser.add_option('-m', '--mode', dest='actions', default='download,install,run,python_test,uninstall',
                  help='Specify what should be done, subset of following (download, install, run, python_test, uninstall)')
parser.add_option('-p', '--platform', dest='platform', default=None, help='Enforce platform (linux, windows, cygwin)')
parser.add_option('-k', '--keep', dest='keep', default=True, help='Abort execution on error', action='store_false')
parser.add_option('-a', '--arch', dest='x64', default=None, help='Enforce bit size (64 or 32)')
parser.add_option('-s', '--server', dest='server', default='http://flow.nti.tul.cz/packages',
                  help='Specify server from which packages will be downloaded, default value is %default')
parser.add_option('-v', '--version', dest='version', default='0.0.master',
                  help='Specify web version identifier which will be part of download url, default value is %default')
parser.add_option('-q', '--quiet', dest='quited', default=False, action="store_true", help='Supress commands output')
options, args = parser.parse_args()

quited = options.quited
action_map = dict(
    download=action_download_package,
    install=action_install,
    run=action_run_flow,
    run_inside=action_run_flow,
    run_outside=action_run_flow,
    python_test=action_python_test,
    python=action_python_test,
    uninstall=action_uninstall
)

action_args = dict(
    server=options.server,
    version=options.version,
    plat=options.platform,
    x64=options.x64,
    ext=None
)

actions = str(options.actions).split(',')
actions_result = dict(zip(actions, len(actions) * ['skipped']))
result = 0
for action in actions:
    print '=' * 100
    print 'Performing action {action:>82}'.format(action=action.upper())
    print '-' * 100
    action_handler = action_map.get(action.strip())
    if action_handler:
        result = action_handler(**action_args)
    else:
        result = 0
        print 'not implemented yet'
    print 'Action {action} exited with {result}\n'.format(action=action.upper(), result=result)
    actions_result[action] = result

    if result != 0 and not options.keep:
        print 'Action {action} failed, exiting script'.format(action=action.upper())
        break

print '=' * 100
print '\n'.join(['{:^100s}'.format('{:<20s} {:^10}'.format(k.upper(), str(actions_result[k]).upper())) for k in actions])
print '=' * 100
exit(result)
