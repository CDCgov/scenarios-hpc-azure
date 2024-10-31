import argparse
import os
from itertools import groupby

from . import EXP_DIR_NAME_OPTIONAL, SECRETS_DIR_NAME, SECRETS_FILE_NAME, utils
from .azure_utils import AzureExperimentLauncher

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
    % EXP_DIR_NAME_OPTIONAL,
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
    default=60,
    help="timeout time in minutes to monitor job, does NOT terminate job after timeout is reached",
)


def launch():
    """The entry point into launching an experiment"""
    args = parser.parse_args()
    experiment_name: str = args.experiment_name
    job_id: str = args.job_id
    cpu_count: int = args.cpu
    timeout_mins: int = args.timeout
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
        experiment_directory=EXP_DIR_NAME_OPTIONAL,
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
