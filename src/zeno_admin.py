import click
from fabric import Connection, ThreadingGroup as Group
from colorama import Fore, Style, init
import os
import sys
import datetime

# Initialize colorama
init(autoreset=True)

def parse_hosts(host_file):
    """Read host addresses from a file, supporting groups [group_name]."""
    if not os.path.exists(host_file):
        raise FileNotFoundError(f"Host file not found: {host_file}")
    
    groups = {"all": []}
    current_group = "all"
    
    try:
        with open(host_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_group = line[1:-1]
                    if current_group not in groups:
                        groups[current_group] = []
                else:
                    groups[current_group].append(line)
                    # Add to 'all' group as well
                    groups["all"].append(line)
    except Exception as e:
        raise IOError(f"Error reading host file: {e}")
    return groups

def log_result(log_file, host, command, result):
    """Log command results to a file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] HOST: {host}\n")
        f.write(f"COMMAND: {command}\n")
        f.write(f"EXIT CODE: {result.exited}\n")
        if result.stdout:
            f.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            f.write(f"STDERR:\n{result.stderr}\n")
        f.write("-" * 60 + "\n")

def execute_command(group, command, use_sudo=False, log_file=None):
    """Execute a command across a group of hosts and display/log the output."""
    try:
        if use_sudo:
            # sudo() handles password prompts and elevation
            results = group.sudo(command, hide=True, warn=True)
        else:
            results = group.run(command, hide=True, warn=True)
    except Exception as e:
        print(f"{Fore.RED}Critical error during execution: {e}")
        return

    for connection, result in results.items():
        host_label = f"{Fore.CYAN}[{connection.host}]{Style.RESET_ALL}"
        
        if result.failed:
            print(f"{host_label} {Fore.RED}FAILED{Style.RESET_ALL} (exit code: {result.exited})")
        else:
            print(f"{host_label} {Fore.GREEN}SUCCESS{Style.RESET_ALL} (exit code: {result.exited})")

        if result.stdout:
            indent = "  "
            formatted_stdout = "\n".join([f"{indent}{line}" for line in result.stdout.strip().split('\n')])
            print(f"{Fore.WHITE}STDOUT:{Style.RESET_ALL}\n{formatted_stdout}")
            
        if result.stderr:
            indent = "  "
            formatted_stderr = "\n".join([f"{indent}{line}" for line in result.stderr.strip().split('\n')])
            print(f"{Fore.RED}STDERR:{Style.RESET_ALL}\n{formatted_stderr}")
            
        if log_file:
            log_result(log_file, connection.host, command, result)
            
        print(Fore.BLACK + Style.BRIGHT + "-" * 40)

@click.group()
def cli():
    """Zeno-SSH - Manage and execute commands across multiple systems."""
    pass

def get_default_hosts_path():
    """Get the path to hosts.txt in the same directory as the script/executable."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try current directory first, then fallback to executable directory
    if os.path.exists("hosts.txt"):
        return "hosts.txt"
    return os.path.join(base_dir, "hosts.txt")

@cli.command()
@click.argument('command')
@click.option('--hosts', '-h', help='Path to the host list file.')
@click.option('--group', '-g', default='all', help='Target a specific group of hosts.')
@click.option('--user', '-u', help='SSH username (optional).')
@click.option('--password', '-p', help='SSH password (optional).')
@click.option('--ask-pass', is_flag=True, help='Prompt for SSH password.')
@click.option('--identity', '-i', type=click.Path(exists=True), help='Path to SSH private key file.')
@click.option('--sudo', is_flag=True, help='Run command with sudo.')
@click.option('--parallel/--no-parallel', default=True, help='Execute commands in parallel.')
@click.option('--log', 'log_enabled', is_flag=True, help='Enable logging to file.')
@click.option('--log-file', default='ssh_admin.log', help='Path to the log file.')
def run(command, hosts, group, user, password, ask_pass, identity, sudo, parallel, log_enabled, log_file):
    """Run a command on all hosts (or a specific group) in the list."""
    try:
        if not hosts:
            hosts = get_default_hosts_path()
            
        all_groups = parse_hosts(hosts)
        if group not in all_groups:
            click.echo(Fore.RED + f"Error: Group '{group}' not found in {hosts}")
            return
            
        host_list = all_groups[group]
        if not host_list:
            click.echo(Fore.YELLOW + f"No hosts found in group '{group}'.")
            return

        # Handle password prompting
        if ask_pass:
            password = click.prompt(f"Password for {user or os.getlogin()}", hide_input=True)

        mode = "parallel" if parallel else "serial"
        sudo_str = " (sudo)" if sudo else ""
        click.echo(Fore.BLUE + f"Executing '{command}' on {len(host_list)} hosts in group '{group}' {mode}{sudo_str}...")
        
        # Connection keyword arguments for identity file and password
        connect_kwargs = {}
        if identity:
            connect_kwargs["key_filename"] = identity
        if password:
            connect_kwargs["password"] = password

        current_log = log_file if log_enabled else None

        if parallel:
            group = Group(*host_list, user=user, connect_kwargs=connect_kwargs)
            execute_command(group, command, use_sudo=sudo, log_file=current_log)
        else:
            for host in host_list:
                # Still use Group of 1 to reuse execute_command logic and formatting
                single_group = Group(host, user=user, connect_kwargs=connect_kwargs)
                execute_command(single_group, command, use_sudo=sudo, log_file=current_log)

    except FileNotFoundError as e:
        click.echo(Fore.RED + f"Error: {e}")
    except Exception as e:
        click.echo(Fore.RED + f"An unexpected error occurred: {e}")

@cli.command()
@click.argument('local_path')
@click.argument('remote_path')
@click.option('--hosts', '-h', help='Path to the host list file.')
@click.option('--group', '-g', default='all', help='Target a specific group.')
@click.option('--user', '-u', help='SSH username.')
@click.option('--password', '-p', help='SSH password.')
@click.option('--ask-pass', is_flag=True, help='Prompt for SSH password.')
@click.option('--identity', '-i', type=click.Path(exists=True), help='Path to private key.')
def put(local_path, remote_path, hosts, group, user, password, ask_pass, identity):
    """Upload a file to multiple hosts."""
    try:
        if not hosts: hosts = get_default_hosts_path()
        all_groups = parse_hosts(hosts)
        targets = all_groups.get(group, []) if group != 'all' else [h for g in all_groups.values() for h in g]
        
        if ask_pass: password = click.prompt("SSH Password", hide_input=True)
        
        click.echo(Fore.CYAN + f"[*] Uploading {local_path} to {remote_path} on {len(targets)} hosts...")
        
        connect_kwargs = {}
        if password: connect_kwargs["password"] = password
        if identity: connect_kwargs["key_filename"] = identity

        group_conn = Group(*targets, user=user, connect_kwargs=connect_kwargs)
        for conn in group_conn:
            try:
                click.echo(Fore.YELLOW + f"[*] {conn.host}: Uploading...")
                conn.put(local_path, remote_path)
                click.echo(Fore.GREEN + f"[+] {conn.host}: Success")
            except Exception as e:
                click.echo(Fore.RED + f"[-] {conn.host}: Error: {e}")

    except Exception as e:
        click.echo(Fore.RED + f"Error: {e}")

@cli.command()
@click.argument('remote_path')
@click.argument('local_path')
@click.option('--hosts', '-h', help='Path to the host list file.')
@click.option('--group', '-g', default='all', help='Target a specific group.')
@click.option('--user', '-u', help='SSH username.')
@click.option('--password', '-p', help='SSH password.')
@click.option('--ask-pass', is_flag=True, help='Prompt for SSH password.')
@click.option('--identity', '-i', type=click.Path(exists=True), help='Path to private key.')
def get(remote_path, local_path, hosts, group, user, password, ask_pass, identity):
    """Download a file from multiple hosts (will append host name to local filename)."""
    try:
        if not hosts: hosts = get_default_hosts_path()
        all_groups = parse_hosts(hosts)
        targets = all_groups.get(group, []) if group != 'all' else [h for g in all_groups.values() for h in g]
        
        if ask_pass: password = click.prompt("SSH Password", hide_input=True)
        
        connect_kwargs = {}
        if password: connect_kwargs["password"] = password
        if identity: connect_kwargs["key_filename"] = identity

        group_conn = Group(*targets, user=user, connect_kwargs=connect_kwargs)
        for conn in group_conn:
            try:
                # Append host to filename to prevent overwriting
                target_local = f"{conn.host}_{local_path}"
                click.echo(Fore.YELLOW + f"[*] {conn.host}: Downloading {remote_path} to {target_local}...")
                conn.get(remote_path, target_local)
                click.echo(Fore.GREEN + f"[+] {conn.host}: Success")
            except Exception as e:
                click.echo(Fore.RED + f"[-] {conn.host}: Error: {e}")

    except Exception as e:
        click.echo(Fore.RED + f"Error: {e}")
