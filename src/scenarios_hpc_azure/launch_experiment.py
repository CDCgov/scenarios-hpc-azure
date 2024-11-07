import argparse
import os
from itertools import groupby

from . import EXP_DIR_NAME, SECRETS_DIR_NAME, SECRETS_FILE_NAME, utils
from .azure_utils import AzureExperimentLauncher

description_str = """a script built to launch experiments created by
the create_experiment script onto CFA's Azure hpc environment.

implicitly this script requires a `secrets/` directory in the current working
directory of the user in order to authenticate with Azure. All Azure
related actions are performed using the `cfa_azure` repository here:
https://github.com/CDCgov/cfa_azure
"""
epilog_str = """Note: the optional --explicit flag is meant to point
to a CSV containing 1 column per flag passed to the `run_task.py`
script running each state. For example if you wish to run 2 states (CA & NC)
each with 2 scenarios (scenario1/2) and your `run_task.py` expects a
`state` and `scenario` flag as command line arguments
your csv would resemble something like: \n
state,scenario\n
CA,scenario1\n
CA,scenario2\n
NC,scenario1\n
NC,scenario2\n

It is important to note that the column titles are passed as the flag names
with a `--` prepended, so the column names are important."""

parser = argparse.ArgumentParser(
    prog="launch_experiment", description=description_str, epilog=epilog_str
)

parser = argparse.ArgumentParser(description="Experiment Azure Launcher")
parser.add_argument(
    "-j",
    "--job_id",
    type=str,
    help="job ID of the azure job, must be unique",
    required=True,
)
parser.add_argument(
    "-e",
    "--experiment_name",
    type=str,
    help="the experiment name, must match the experiment directory within %s"
    % EXP_DIR_NAME,
    required=True,
)
parser.add_argument(
    "-c",
    "--cpu",
    type=int,
    required=False,
    default=8,
    help="CPU count of machines running each task, supports 2, 4, or 8 cores",
)

parser.add_argument(
    "-t",
    "--timeout",
    type=int,
    required=False,
    default=600,
    help="timeout time in minutes to monitor job, does NOT terminate job after timeout is reached",
)

parser.add_argument(
    "--explicit",
    type=str,
    required=False,
    help="path to optional explicit task arguments csv",
)


def launch():
    """The entry point into launching an experiment"""
    args = parser.parse_args()
    experiment_name: str = args.experiment_name
    job_id: str = args.job_id
    cpu_count: int = args.cpu
    timeout_mins: int = args.timeout
    # explicit_csv_path: str = args.explicit
    docker_image_tag = "scenarios_image_%s" % job_id
    print(
        f"""{utils.bcolors.OKGREEN}Launching experiment {experiment_name}
        under jobid {job_id} with {cpu_count} cpu machines{utils.bcolors.ENDC}
        """
    )
    azure_config_toml_path = os.path.join(
        os.getcwd(), SECRETS_DIR_NAME, SECRETS_FILE_NAME
    )

    postprocess_execution_order = []
    # upload dockerfile used
    launcher = AzureExperimentLauncher(
        experiment_name,
        job_id,
        azure_config_toml=azure_config_toml_path,
        experiment_directory=EXP_DIR_NAME,
        docker_image_name=docker_image_tag,
    )
    pp_scripts_path = os.path.join(
        launcher.experiment_path_local, "postprocessing_scripts"
    )
    if os.path.exists(pp_scripts_path):
        postprocess_script_filenames = [
            f
            for f in os.listdir(pp_scripts_path)
            if os.path.isfile(os.path.join(pp_scripts_path, f))
        ]
        # Sort the list based on the numeric prefix of each filename
        sorted_list = sorted(
            postprocess_script_filenames, key=lambda x: int(x.split("_")[0])
        )

        # Group the filenames based on their shared numbers
        postprocess_execution_order = [
            list(group)
            for _, group in groupby(sorted_list, lambda x: x.split("_")[0])
        ]

    launcher.set_resource_pool(pool_name="scenarios_%scpu_pool" % cpu_count)
    all_tasks_run = []
    state_task_ids = launcher.launch_states()
    postprocessing_tasks = launcher.launch_postprocess(
        execution_order=postprocess_execution_order,
        depend_on_task_ids=state_task_ids,
    )
    all_tasks_run += state_task_ids + postprocessing_tasks
    launcher.azure_client.monitor_job(job_id, timeout=timeout_mins)
