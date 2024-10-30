import argparse

parser = argparse.ArgumentParser()
# experiment directory
parser.add_argument(
    "-e",
    "--experiment_name",
    type=str,
    required=True,
    help="str, name of the experiment states should be placed into",
)
# list of fips codes
parser.add_argument(
    "-s",
    "--states",
    type=str,
    required=True,
    nargs="+",
    help="space separated list of str representing USPS postal code of each state",
)
parser.add_argument(
    "-m",
    "--config_molds",
    type=str,
    required=False,
    nargs="+",
    help="space separated paths to the config molds, defaults to the template_configs directory within the experiment",
)
args = parser.parse_args()
print(args)


def create():
    print("testing creation of experiments")
