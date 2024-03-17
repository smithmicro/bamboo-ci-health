#!/usr/bin/env python3
"""
ci_health.py
============

A command-line tool for generating HTML reports from Bamboo MySQL database.

Reporting process:
1. Query MySQL: `SELECT BUILD_ID, ..., UPDATED_DATE FROM BUILD WHERE BUILD_TYPE IN ('CHAIN_BRANCH', 'CHAIN');`
2. Get records like these:
   ```plain
            BUILD_ID: 35095049
          BUILD_TYPE: CHAIN_BRANCH
            FULL_KEY: NW-CND43
               TITLE: 4_00_20_0057
         DESCRIPTION: Branch for Croffox releases from commit 421cd90 (4.00.20.0057 release) and selective commits
   LINKED_JIRA_ISSUE: NULL
        CREATED_DATE: 2017-02-01 03:45:44
        UPDATED_DATE: 2022-06-18 06:19:05
   ```
3. For each `BUILD_ID`, check if it has artifacts, i.e. a `$BAMBOO_HOME/shared/artifacts/plan-${BUILD_ID}` directory
4. Get the size of each build plan's artifact directory
5. Check for orphaned artifact directories in the `$BAMBOO_HOME/shared/artifacts/` directory
6. Compile an HTML report with links to build plans and save it under `/usr/share/nginx/html/static/ci-health/`

To expose the generated reports to outside viewers, update the Nginx config to serve `$NGINX_ROOT/static/ci-health/` as
a static file directory on the `<bamboo_host>/static/ci-health/` URL.
"""
import datetime
import os
from typing import Union

import click
import sh
import pandas as pd
import xml.etree.ElementTree as ET
from hurry.filesize import size as hurry_size


def _get_build_artifact_size(row: pd.Series, debug=False) -> pd.Series:
    """Get the size of the artifact directory for a build ID in `--bamboo-home`."""
    artifact_dir = row['FS_ARTIFACT_DIR']
    artifact_size = int(sh.du("-s", artifact_dir).split()[0])
    if debug:
        click.echo(f"Artifact size for build plan '{artifact_dir}' is {artifact_size} kilobytes...")
    row['FS_ARTIFACT_SIZE'] = artifact_size * 1024
    row['FS_ARTIFACT_DATE'] = datetime.datetime.utcnow().replace(microsecond=0)
    return row


@click.group()
@click.option('--debug/--no-debug', default=False, help="Print debug information")
@click.option('--tmp-dir', default=f'{os.getcwd()}/tmp',
              type=click.Path(file_okay=False, resolve_path=True), help="Working directory for raw reporting data")
@click.option('--bamboo-home', default=f'/opt/bamboo-master-home',
              type=click.Path(file_okay=False, resolve_path=True, exists=True, readable=True),
              help="Bamboo master home directory")
@click.pass_context
def cli(ctx: any, debug: bool, tmp_dir: str, bamboo_home: str, max_content_width=120, help_option=False):
    """Main entry point for running the report creation sub-command sequence.

    The tool expects you to specify $BAMBOO_HOME and temp dir, then run the sub-commands in the following order:

    \b
    1. ./ci_health.py --tmp-dir=/tmp/ci-health --bamboo-home=/opt/bamboo-master-home 1a-init-db-builds
    2. ./ci_health.py --tmp-dir=/tmp/ci-health --bamboo-home=/opt/bamboo-master-home 1b-init-fs-artifacts
    3. ./ci_health.py --tmp-dir=/tmp/ci-health --bamboo-home=/opt/bamboo-master-home 1c-find-orphans
    4. ./ci_health.py --tmp-dir=/tmp/ci-health --bamboo-home=/opt/bamboo-master-home 2-generate-reports --output-dir=/usr/share/nginx/html/static/ci-health
    """
    os.makedirs(tmp_dir, exist_ok=True)
    if debug:
        click.echo(f"Debug mode is on")
        click.echo(f"Temporary reports/data directory is {tmp_dir}")
        click.echo(f"BAMBOO_HOME directory is {bamboo_home}")
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    ctx.obj['TMP_DIR'] = tmp_dir
    ctx.obj['BAMBOO_HOME'] = bamboo_home


@cli.command('1a-init-db-builds')
@click.option('--limit', default=None, type=int)
@click.pass_context
def init_db_builds(ctx, limit: int, max_content_width=120):
    """Initialize Bamboo builds data from MySQL, stored to `--tmp-dir`."""

    def _get_db_credentials_from_bamboo_cfg(bamboo_home: str, debug: False) -> [str, str, str]:
        """Get the username, password and hostname for the Bamboo database from `{--bamboo-home}/bamboo.cfg.xml`."""
        bamboo_cfg = f"{bamboo_home}/bamboo.cfg.xml"
        if not os.path.isfile(bamboo_cfg):
            click.echo(
                f"Bamboo config file '{bamboo_cfg}' not found, did you specify the correct `./ci_health --bamboo-home`?"
            )
            exit(1)
        try:
            tree = ET.parse(bamboo_cfg)
            root = tree.getroot()
            app_config = root.find('properties')
            db_host, db_user, db_passwd = None, None, None
            for config_property in app_config.findall('./property'):
                if config_property.get('name') == 'hibernate.connection.url':
                    db_host = config_property.text.split("jdbc:mysql://")[1].split("/bamboo")[0]
                    if debug:
                        click.echo(f"Found database host in {config_property.get('name')}: {db_host}")
                if config_property.get('name') == 'hibernate.connection.username':
                    db_user = config_property.text
                    if debug:
                        click.echo(f"Found database user in {config_property.get('name')}: {db_user}")
                if config_property.get('name') == 'hibernate.connection.password':
                    db_passwd = config_property.text
                    if debug:
                        click.echo(f"Found database password in {config_property.get('name')}: {'*' * len(db_passwd)}")
            if all([db_host, db_user, db_passwd]):
                return db_host, db_user, db_passwd
            else:
                click.echo(f"Database credentials not fully identified in Bamboo config file '{bamboo_cfg}'")
                exit(1)
        except Exception as e:
            click.echo(f"Error parsing Bamboo config file '{bamboo_cfg}': {e}")
            exit(1)

    def _query_mysql_for_builds(db_host: str, db_user: str, db_passwd: str, limit_: int = None) -> pd.DataFrame:
        """Query MySQL database for 'CHAIN_BRANCH' and 'CHAIN' type builds."""
        query = f"""
            SELECT
                BUILD_ID, BUILD_TYPE, FULL_KEY, TITLE, DESCRIPTION, LINKED_JIRA_ISSUE, CREATED_DATE, UPDATED_DATE
            FROM
                build
            -- WHERE
            --     BUILD_TYPE IN ('CHAIN_BRANCH', 'CHAIN', 'BUILD')
            {'LIMIT ' + str(limit_) if limit_ else ''}
        """
        return pd.read_sql(query, f"mysql+pymysql://{db_user}:{db_passwd}@{db_host}/bamboo")

    df = _query_mysql_for_builds(*_get_db_credentials_from_bamboo_cfg(ctx.obj['BAMBOO_HOME'], ctx.obj['DEBUG']),
                                 limit_=limit)
    if ctx.obj['DEBUG']:
        click.echo(f"Database builds DataFrame:")
        click.echo(df)
    dump_path = f"{ctx.obj['TMP_DIR']}/db_bamboo_builds_t0.pkl"
    df.to_pickle(dump_path)
    click.echo(f"Database builds DataFrame dumped to {dump_path}")


@cli.command('1b-init-fs-artifacts')
@click.pass_context
def init_fs_artifacts(ctx):
    """Initialize Bamboo build artifact sizes from filesystem, stored to `--tmp-dir`."""

    def _get_build_artifact_dir(build_id: int, bamboo_home: str, debug=False) -> Union[str, any]:
        """Get the artifact directory for a build ID in `--bamboo-home`."""
        artifact_dir = f"{bamboo_home}/shared/artifacts/plan-{build_id}"
        if os.path.isdir(artifact_dir):
            if debug:
                click.echo(f"Artifact directory found: '{artifact_dir}'...")
            return artifact_dir
        else:
            return pd.NA

    dump_path_db = f"{ctx.obj['TMP_DIR']}/db_bamboo_builds_t0.pkl"
    if not os.path.isfile(dump_path_db):
        click.echo(
            f"Database builds DataFrame not found at {dump_path_db}, did you run `./ci_health.py init-db-builds`?"
        )
        exit(1)
    df = pd.read_pickle(dump_path_db)
    if ctx.obj['DEBUG']:
        click.echo(f"Database builds DataFrame read from {dump_path_db}:")
        click.echo(df)
    # Add a separate column to the DataFrame with the artifact directory (if it exists)
    df['FS_ARTIFACT_DIR'] = df['BUILD_ID'].apply(_get_build_artifact_dir,
                                                 args=[ctx.obj['BAMBOO_HOME'], ctx.obj['DEBUG']])
    df_with_artifact_dirs = df[df['FS_ARTIFACT_DIR'].notna()]
    if ctx.obj['DEBUG']:
        click.echo('Builds with artifact directories DataFrame:')
        click.echo(df_with_artifact_dirs)
    # Add two separate columns to the DataFrame with the size of the artifact directory and the date of the size check
    df_with_artifact_sizes = df_with_artifact_dirs.apply(_get_build_artifact_size, args=[ctx.obj['DEBUG']], axis=1)
    dump_path_fs = f"{ctx.obj['TMP_DIR']}/fs_bamboo_builds_t0.pkl"
    df_with_artifact_sizes.to_pickle(dump_path_fs)
    if ctx.obj['DEBUG']:
        click.echo(f"Filesystem builds DataFrame:")
        click.echo(df_with_artifact_sizes)
    # Done with the filesystem builds DataFrame
    click.echo(f"Filesystem builds DataFrame dumped to {dump_path_fs}")


@cli.command('1c-find-orphans')
@click.pass_context
def find_orphans(ctx):
    """Find orphaned artifact directories in the $BAMBOO_HOME/shared/artifacts/ directory."""
    dump_path_fs = f"{ctx.obj['TMP_DIR']}/fs_bamboo_builds_t0.pkl"
    if not os.path.isfile(dump_path_fs):
        click.echo(
            f"Filesystem builds DataFrame not found at {dump_path_fs}, did you run `./ci_health.py init-fs-artifacts`?"
        )
        exit(1)

    df_fs = pd.read_pickle(dump_path_fs)
    orphaned_dirs = []
    for build_dir in os.scandir(f"{ctx.obj['BAMBOO_HOME']}/shared/artifacts"):
        dir_path = f"{ctx.obj['BAMBOO_HOME']}/shared/artifacts/{build_dir.name}"
        if build_dir.name in {'tmp', 'globalStorage'}:
            click.echo(f"Ignore special sub-directory '{dir_path}'...")
            continue
        if dir_path not in list(df_fs['FS_ARTIFACT_DIR']):
            orphaned_dirs.append(dir_path)
            if ctx.obj['DEBUG']:
                click.echo(f"Found orphaned directory: {build_dir.name}")
    click.echo(f"Found {len(orphaned_dirs)} orphaned directories, from a total {len(df_fs)} known artifact build dirs.")
    orphans_df = pd.DataFrame(orphaned_dirs, columns=['FS_ARTIFACT_DIR'])
    orphans_df_with_artifact_sizes = orphans_df.apply(_get_build_artifact_size, args=(ctx.obj['DEBUG'],), axis=1)
    dump_path_orphans = f"{ctx.obj['TMP_DIR']}/fs_bamboo_orphans_t0.pkl"
    orphans_df_with_artifact_sizes.to_pickle(dump_path_orphans)
    if ctx.obj['DEBUG']:
        click.echo(f"Filesystem orphans DataFrame:")
        click.echo(orphans_df_with_artifact_sizes)
    # Done with the orphans builds DataFrame
    click.echo(f"Filesystem orphans DataFrame dumped to {dump_path_orphans}")


@cli.command('2-generate-reports')
@click.option('--output-dir', default=f'/usr/share/nginx/html/static/ci-health',
              type=click.Path(file_okay=False, resolve_path=True))
@click.pass_context
def generate_reports(ctx, output_dir: str):
    """Generate HTML reports from Bamboo builds data and artifact directory sizes."""
    dump_path_db = f"{ctx.obj['TMP_DIR']}/db_bamboo_builds_t0.pkl"
    if not os.path.isfile(dump_path_db):
        click.echo(
            f"Database builds DataFrame not found at {dump_path_db}, did you run `./ci_health.py init-db-builds`?"
        )
        exit(1)
    dump_path_fs = f"{ctx.obj['TMP_DIR']}/fs_bamboo_builds_t0.pkl"
    if not os.path.isfile(dump_path_fs):
        click.echo(
            f"Filesystem builds DataFrame not found at {dump_path_fs}, did you run `./ci_health.py init-fs-artifacts`?"
        )
        exit(1)

    # Prepare output directories
    reports_archive_dir = f"{output_dir}/archive"
    os.makedirs(reports_archive_dir, mode=0o775, exist_ok=True)
    if ctx.obj['DEBUG']:
        click.echo(f"Writing reports to `--output-dir` '{output_dir}' (archive dir '{reports_archive_dir}')`:")
        click.echo(sh.ls('-lFah', output_dir, reports_archive_dir))

    # Read raw report data
    df_fs = pd.read_pickle(dump_path_fs)

    df_with_artifact_gt1mb = df_fs[df_fs['FS_ARTIFACT_SIZE'] > 1024**2]
    # if ctx.obj['DEBUG']:
    #     click.echo(f"Builds DataFrame with shared artifact sizes > 1MB:")
    #     click.echo(df_with_artifact_gt1mb)

    df_with_clickable_links = df_with_artifact_gt1mb.copy()
    df_with_clickable_links['PLAN_LINK'] = df_with_clickable_links['FULL_KEY'].apply(
        lambda full_key: f'<a href="/browse/{full_key}" target="_blank">{full_key}</a>'
    )
    # if ctx.obj['DEBUG']:
    #     click.echo(f"Builds DataFrame with clickable links:")
    #     click.echo(df_with_clickable_links)

    df_sorted_by_size = df_with_clickable_links.sort_values(by='FS_ARTIFACT_SIZE', ascending=False)
    df_sorted_by_size['DISK_SIZE'] = df_sorted_by_size['FS_ARTIFACT_SIZE'].apply(hurry_size)
    # if ctx.obj['DEBUG']:
    #     click.echo(f"Builds DataFrame sorted by artifact size:")
    #     click.echo(df_sorted_by_size)

    # Update DataFrame with columns for report and write to HTML and pickle files
    df_sorted_by_size['CHECKED_DATE'] = df_sorted_by_size['FS_ARTIFACT_DATE']
    df_sorted_by_size['TYPE'] = df_sorted_by_size['BUILD_TYPE'].apply(lambda type_: type_.split('_')[-1])
    df_columns_for_report = df_sorted_by_size[
        ['TYPE', 'TITLE', 'PLAN_LINK', 'CREATED_DATE', 'UPDATED_DATE', 'CHECKED_DATE', 'DISK_SIZE']
    ]
    if ctx.obj['DEBUG']:
        click.echo(f"Builds DataFrame columns for report:")
        click.echo(df_columns_for_report)
    archive_date = datetime.datetime.utcnow()
    archive_file = f"{reports_archive_dir}/{archive_date.strftime('%y%m%dT%HZ')}_plans_by_shared_artifact_size_desc"
    click.echo(f"Writing report to '{output_dir}/index.html', '{archive_file}.html', and '{archive_file}.pkl'")
    df_columns_for_report.to_html(f"{archive_file}.html", escape=False, index=False)
    df_columns_for_report.to_pickle(f"{archive_file}.pkl")
    df_columns_for_report.to_html(f"{output_dir}/index.html", escape=False, index=False)


if __name__ == '__main__':
    cli(obj={}, max_content_width=120)

