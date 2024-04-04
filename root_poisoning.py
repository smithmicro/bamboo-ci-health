#!/usr/bin/env python3
"""
root_poisoning.py
=================

A command-line tool for finding build plans that leave root-owned files in Bamboo Agent homes dirs and reporting on it.

A pre-requisite for this process to work is that you have a bunch of remote agents and a nightly cron job on each agent:

```cron
#Ansible: daily-bamboo-home-chowning
1 5 * * * bash /root/daily-bamboo-home-chowning.sh
```

The `daily-bamboo-home-chowning.sh` script should look something like this:

```bash
#!/bin/bash

for assetDir in bamboo-agent-home .cache .m2 .npm .java .gradle .android; do
  if [ -d /home/bamboo/$assetDir ]; then
    chown -vR bamboo:bamboo /home/bamboo/$assetDir | grep -v retained >> \
      "/home/bamboo/$(date +'%y%m%d')_bamboo-home-assets-chowned.log"
  fi
done
```

The cron job will create a daily log file in the Bamboo user's home directory with ownership corrections, like so:

```plain
head -n 5 /home/bamboo/240404_bamboo-home-assets-chowned.log
"changed ownership of '/home/bamboo/bamboo-agent-home/xml-data/build-dir/121667592-127238147/source-code/clusters/opovo/environment-configuration.json' from root:root to bamboo:bamboo"
"changed ownership of '/home/bamboo/bamboo-agent-home/xml-data/build-dir/121667592-127238147/source-code/clusters/opovo' from root:root to bamboo:bamboo"
"changed ownership of '/home/bamboo/bamboo-agent-home/xml-data/build-dir/121667587-121602106/ssh/known_hosts' from root:root to bamboo:bamboo"
"changed ownership of '/home/bamboo/bamboo-agent-home/xml-data/build-dir/121667587-121602106/deployment.vars' from root:root to bamboo:bamboo"
"changed ownership of '/home/bamboo/bamboo-agent-home/xml-data/build-dir/BEXP-SAFEAUTO-JOB1/automation/restApi/build/reports/gatling' from root:root to bamboo:bamboo"
```

To run the reporting process you need a private SSH key that can be used to retrieve the log files from each agent.

The reporting process is as follows:
1. Retrieve the daily log files from each agent and store them in a local temp directory
2. Parse the log files for changed file paths and their deployment keys and build job keys
3. Compile an HTML report with links to de-duplicated build jobs and deployments, save it in
   `/usr/share/nginx/html/static/root-poisoned/` to expose externally

To expose the generated reports to outside viewers, update the Nginx config to serve `$NGINX_ROOT/static/root-poisoned/`
as a static file directory on the `<bamboo_host>/static/ci-health/` URL.
"""
import datetime
import os
import sys

import click
import sh
import pandas as pd


def _get_todays_temp_dir(tmp_dir: str, todays_date: str) -> str:
    """Get the temp directory for today's date (create if needed)."""
    todays_temp_dir = f"{tmp_dir}/{todays_date}_root-poisoning"
    os.makedirs(todays_temp_dir, exist_ok=True)
    return todays_temp_dir


@click.group()
@click.option('--debug/--no-debug', default=False, help="Print debug information")
@click.option('--tmp-dir', default=f'{os.getcwd()}/tmp',
              type=click.Path(file_okay=False, resolve_path=True), help="Working directory for raw reporting data")
@click.option('--todays-date', default=None, type=str, help="Override today's date for back-fill/testing")
@click.pass_context
def cli(ctx: any, debug: bool, tmp_dir: str, todays_date=None, max_content_width=120, help_option=False):
    """Main entry point for running the report creation sub-command sequence.

    The tool expects you to specify a temp dir, then run the sub-commands in the following order:

    \b
    1. ./root_poisoning.py --tmp-dir=/tmp/ci-health 1-retrieve-todays-logs bamboo ~/.ssh/id_rsa agent-1 agent-2 agent-3
    2. ./root_poisoning.py --tmp-dir=/tmp/ci-health 2-parse-todays-logs
    1. ./root_poisoning.py --tmp-dir=/tmp/ci-health 3-generate-todays-reports --output-dir=/usr/share/nginx/html/static/root-poisoned
    """
    os.makedirs(tmp_dir, exist_ok=True)
    todays_date = todays_date if todays_date else sh.date('+%y%m%d').strip()
    if debug:
        click.echo(f"Debug mode is on")
        click.echo(f"Temporary reports/data directory is {tmp_dir}")
        click.echo(f"Today's date is '{todays_date}'")
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    ctx.obj['TMP_DIR'] = tmp_dir
    ctx.obj['TODAYS_DATE'] = todays_date


@cli.command('1-retrieve-todays-logs')
@click.argument('bamboo_agent_ssh_user', type=str, required=True)
@click.argument('bamboo_agent_ssh_key', type=click.Path(file_okay=True, dir_okay=False, resolve_path=True,
                                                        exists=True, readable=True))
@click.argument('bamboo_agent_hostnames', nargs=-1, type=str, required=True)
@click.pass_context
def retrieve_todays_logs(ctx, bamboo_agent_ssh_user: str, bamboo_agent_ssh_key: str, bamboo_agent_hostnames: tuple,
                         max_content_width=120):
    """Retrieve today's chown'ing logs from each of the Bamboo agents, stored to `--tmp-dir`/%y%m%d_root-poisoning/."""

    # Get today's date (temp dir) and the remote log filename
    todays_date = ctx.obj['TODAYS_DATE']
    tmp_base_dir = _get_todays_temp_dir(ctx.obj['TMP_DIR'], todays_date)
    remote_log_filename = f"/home/bamboo/{todays_date}_bamboo-home-assets-chowned.log"
    click.echo(f"Retrieve daily log file '{remote_log_filename}' to '{tmp_base_dir}', from "
               f"agents {', '.join(bamboo_agent_hostnames)}...")

    # Copy the private SSH key to a temporary location and correct its permissions
    copied_private_key_path = f"{tmp_base_dir}/bamboo-agent-ssh-key"
    if ctx.obj['DEBUG']:
        click.echo(f"Copy '{bamboo_agent_ssh_key}' to '{copied_private_key_path}' and corrected ownership:")
    sh.cp('-v', bamboo_agent_ssh_key, copied_private_key_path)
    sh.chmod('0600', copied_private_key_path)
    if ctx.obj['DEBUG']:
        sh.ls('-lFah', copied_private_key_path, _out=sys.stdout).strip('\n')

    for hostname in bamboo_agent_hostnames:
        local_log_filename = f"{tmp_base_dir}/todays_{hostname}_bamboo-home-assets-chowned.log"
        if ctx.obj['DEBUG']:
            click.echo(
                f"Retrieving daily log file from '{hostname}' to '{local_log_filename}' as '{bamboo_agent_ssh_user}'..."
            )
        sh.scp("-i", copied_private_key_path, "-o", "StrictHostKeyChecking=no",
               f"{bamboo_agent_ssh_user}@{hostname}:{remote_log_filename}", local_log_filename)

    if ctx.obj['DEBUG']:
        click.echo(f"Fry the private SSH key '{copied_private_key_path}'...")
    sh.rm('-f', copied_private_key_path)

    click.echo(f"Today's log files retrieved from agents and stored to '{tmp_base_dir}':")
    sh.ls('-lFah', _cwd=tmp_base_dir, _out=sys.stdout).strip('\n')


@cli.command('2-parse-todays-logs')
@click.pass_context
def parse_todays_logs(ctx):
    """Parse today's logs in `--tmp-dir`/%y%m%d_root-poisoning/."""

    def _parse_log_file(log_file_path: str, debug=False) -> pd.DataFrame:
        """Parse a log file and return a DataFrame with the data in separate columns."""
        hostname_short = log_file_path.split('/')[-1].split('_')[1].split('.smithmicro.net')[0]
        log_lines = []
        with open(log_file_path, 'r') as f:
            for line in f.readlines():
                if 'changed ownership of ' in line and ' from root:root to bamboo:bamboo' in line:
                    file_path_and_ownership = line.strip().split('changed ownership of ')[-1]
                    filepath = file_path_and_ownership.split(' from root:root to bamboo:bamboo')[0].strip("'‘’")
                    if filepath.startswith("/home/bamboo/bamboo-agent-home/xml-data/"):
                        rel_filepath = filepath.split('/home/bamboo/bamboo-agent-home/')[-1]
                        job_or_deployment_key = rel_filepath.split('/')[2]
                        build_job = job_or_deployment_key if job_or_deployment_key.count('-') == 2 else pd.NA
                        deployment = job_or_deployment_key if job_or_deployment_key.count('-') == 1 else pd.NA
                        assert (
                            isinstance(build_job, str) or isinstance(deployment, str)
                        ), f"Invalid build job or deployment '{job_or_deployment_key}'!"
                        tasks_local_path = rel_filepath.split('/', 3)[3]
                        poisoned_bamboo_home_path = '$BAMBOO_HOME/' + '/'.join(rel_filepath.split('/')[:3])
                        log_lines.append(
                            [poisoned_bamboo_home_path, job_or_deployment_key, build_job, deployment, tasks_local_path]
                        )
                    else:
                        click.echo(f"WARN: Ignored non-build plan file '{filepath}' on {hostname_short}!")
        log_file_df = pd.DataFrame(log_lines, columns=[
            'POISONED_BAMBOO_HOME_PATH', 'KEY_ID', 'BUILD_JOB', 'DEPLOYMENT', 'LOCAL_PATH_FOR_BUILD_OR_DEPLOYMENT_TASKS'
        ])
        log_file_df['FOUND_ON_AGENT_HOSTS'] = hostname_short
        # if debug:
        #     click.echo(f"Log file '{log_file_path}' parsed to DataFrame:")
        #     click.echo(log_file_df)
        return log_file_df

    # Get log files in today's temp dir
    todays_temp_dir = _get_todays_temp_dir(ctx.obj['TMP_DIR'], ctx.obj['TODAYS_DATE'])
    if not os.path.isdir(todays_temp_dir):
        click.echo(f"Today's temp directory '{todays_temp_dir}' not found, did you run `./root_poisoning.py "
                   f"1-retrieve-todays-logs <agent_ssh_user> <agent_ssh_key> <bamboo_agent_hostnames...>`?")
        exit(1)
    log_files = sh.find(todays_temp_dir, '-name', '*_bamboo-home-assets-chowned.log').split()
    click.echo(f"Found {len(log_files)} log files to parse in '{todays_temp_dir}'...")

    # Parse each log file into a DataFrame
    log_file_dataframes = []
    for log_file in log_files:
        log_file_dataframes.append(_parse_log_file(log_file, ctx.obj['DEBUG']))

    # Concatenate all logs into a single DataFrame
    all_log_files_df = pd.concat(log_file_dataframes, ignore_index=True)
    dump_path = f"{todays_temp_dir}/todays_bamboo-home-assets-chowned.pkl"
    all_log_files_df.to_pickle(dump_path)
    if ctx.obj['DEBUG']:
        click.echo(f"Full root-poisoning logs DataFrame for today:")
        click.echo(all_log_files_df)

    # Done with the log files DataFrame
    click.echo(f"Root-poisoning logs DataFrame dumped to '{dump_path}'")


@cli.command('3-generate-todays-reports')
@click.option('--output-dir', default=f'/usr/share/nginx/html/static/root-poisoned',
              type=click.Path(file_okay=False, resolve_path=True))
@click.pass_context
def generate_todays_reports(ctx, output_dir: str):
    """Generate HTML reports from today's root-poisoning logs."""

    todays_date = ctx.obj['TODAYS_DATE']
    todays_temp_dir = _get_todays_temp_dir(ctx.obj['TMP_DIR'], todays_date)
    dump_path = f"{todays_temp_dir}/todays_bamboo-home-assets-chowned.pkl"
    if not os.path.isfile(dump_path):
        click.echo(
            f"Root-poisoning logs not found at {dump_path}, did you run `./root_poisoning.py 2-parse-todays-logs`?"
        )
        exit(1)

    # Prepare output directories
    reports_archive_dir = f"{output_dir}/archive"
    os.makedirs(reports_archive_dir, mode=0o775, exist_ok=True)
    if ctx.obj['DEBUG']:
        click.echo(f"Writing reports to `--output-dir` '{output_dir}' (archive dir '{reports_archive_dir}')`:")
        click.echo(sh.ls('-lFah', output_dir, reports_archive_dir).strip('\n'))

    # Read raw report data
    all_log_files_df = pd.read_pickle(dump_path)

    # Get unique build jobs and deployments
    unique_build_jobs = all_log_files_df['BUILD_JOB'].unique()
    unique_deployments = all_log_files_df['DEPLOYMENT'].unique()
    if ctx.obj['DEBUG']:
        click.echo(f"Found {len(unique_build_jobs)} unique build jobs and "
                   f"{len(unique_deployments)} unique deployments...")

    def _summarize_hosts(hosts: pd.Series) -> str:
        """Summarize the unique hosts for a build job or a deployment."""
        unique_hosts = hosts.unique()
        html_unique_hosts = list(map(lambda host: f"<code>{host}</code>", unique_hosts))
        return ', '.join(html_unique_hosts)

    def _summarize_local_paths(local_paths: pd.Series) -> str:
        """Summarize the unique workspace-local root-poisoned file paths for a build job or a deployment."""
        unique_paths = local_paths.unique()
        max_paths = 100
        html_unique_paths = list(map(lambda path: f"<code>{path}</code>", unique_paths))
        if len(html_unique_paths) > max_paths:
            return f"{', '.join(html_unique_paths[:max_paths])}... ({len(html_unique_paths) - max_paths} more)"
        return ', '.join(html_unique_paths)

    # Group by build job and deployment
    grouped_by_build_job_and_deployment = all_log_files_df.groupby('KEY_ID').agg({
        'POISONED_BAMBOO_HOME_PATH': 'first',
        'BUILD_JOB': 'first',
        'DEPLOYMENT': 'first',
        'FOUND_ON_AGENT_HOSTS': _summarize_hosts,
        'LOCAL_PATH_FOR_BUILD_OR_DEPLOYMENT_TASKS': _summarize_local_paths
    })

    # Prepare DataFrame for report
    if ctx.obj['DEBUG']:
        click.echo(f"Hosts and local file paths grouped by build job and deployment:")
        click.echo(grouped_by_build_job_and_deployment)

    grouped_by_build_job_and_deployment['BUILD_JOB_LINK'] = grouped_by_build_job_and_deployment['BUILD_JOB'].apply(
        lambda build_job: (f'<a href="/browse/{build_job}/latest" target="_blank"><pre>{build_job}</pre></a>'
                           if build_job else '')
    )

    grouped_by_build_job_and_deployment['DEPLOYMENT_LINK'] = grouped_by_build_job_and_deployment['DEPLOYMENT'].apply(
        lambda deployment: (f'<a href="/deploy/viewEnvironment.action?id={deployment.split("-")[1]}" '
                            f'target="_blank"><pre>{deployment}</pre></a>') if deployment else ''
    )

    grouped_by_build_job_and_deployment['POISONED_BAMBOO_HOME_PATH'] = grouped_by_build_job_and_deployment[
        'POISONED_BAMBOO_HOME_PATH'].apply(lambda home_path: f"<pre>{home_path}/</pre>")

    # Update DataFrame with columns for report and write to HTML and pickle files
    df_columns_for_report = grouped_by_build_job_and_deployment[[
        'BUILD_JOB_LINK', 'DEPLOYMENT_LINK', 'POISONED_BAMBOO_HOME_PATH', 'LOCAL_PATH_FOR_BUILD_OR_DEPLOYMENT_TASKS',
        'FOUND_ON_AGENT_HOSTS'
    ]]
    if ctx.obj['DEBUG']:
        click.echo(f"Builds DataFrame columns for report:")
        click.echo(df_columns_for_report)

    archive_date = datetime.datetime.utcnow()
    archive_file = (f"{reports_archive_dir}/"
                    f"{archive_date.strftime('%y%m%dT%HZ')}_root_poisoned_build_jobs_and_deployments_{todays_date}")

    click.echo(f"Writing report to '{output_dir}/index.html', '{archive_file}.html', and '{archive_file}.pkl'")
    df_columns_for_report.to_html(f"{archive_file}.html", escape=False, index=False)
    df_columns_for_report.to_pickle(f"{archive_file}.pkl")
    df_columns_for_report.to_html(f"{output_dir}/index.html", escape=False, index=False)


if __name__ == '__main__':
    cli(obj={}, max_content_width=120)

