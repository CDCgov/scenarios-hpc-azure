import argparse
import os

EXPERIMENTS_DIRECTORY = os.getcwd()

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
    % EXPERIMENTS_DIRECTORY,
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
args = parser.parse_args()
experiment_name: str = args.experiment_name
job_id: str = args.job_id
cpu_count: int = args.cpu


def launch():
    print(
        "Launching experiment %s under jobid %s with %s cpu machines"
        % (
            experiment_name,
            job_id,
            cpu_count,
        )
    )
    print("example launching of the experiment from %s" % str(os.getcwd()))
