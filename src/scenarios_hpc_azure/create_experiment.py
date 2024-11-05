import argparse
import os

import pandas as pd

from . import (
    EXP_DIR_NAME,
    PP_SCRIPTS_DIR_NAME,
    REGION_INFO_PATH,
    STATE_CONFIGS_DIR_NAME,
    TEMPLATE_CONFIGS_DIR_NAME,
    utils,
)

description_str = """a script built to generate states/region specific config files
from a set of template configs. Given an experiment name that
matches a directory within `%s`, reads template configs from within the
experiment's `%s` dir and programatically copies them over to
state/region specific configs within the experiment's `%s` directory.""" % (
    EXP_DIR_NAME,
    TEMPLATE_CONFIGS_DIR_NAME,
    STATE_CONFIGS_DIR_NAME,
)
epilog_str = (
    """NOTE: running experiment_creator multiple times on the same
experiment will cause all state/region configs within the experiment's %s
directory to be cleared each time."""
    % STATE_CONFIGS_DIR_NAME
)

parser = argparse.ArgumentParser(
    prog="create_experiment", description=description_str, epilog=epilog_str
)
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
    help="space separated list of str representing "
    "USPS postal code of each state. Can also be `all` or `50state` for "
    "all available regions or just 50 states respectively.",
)
parser.add_argument(
    "-tc",
    "--template_configs",
    type=str,
    required=False,
    nargs="+",
    help="space separated paths to the template configs, defaults to the %s directory within the experiment"
    % TEMPLATE_CONFIGS_DIR_NAME,
)


def create():
    """Entry point to the create_experiment script, meant to be executed
    from directory in which experiment exists.
    """
    args = parser.parse_args()
    experiment_name: str = args.experiment_name
    states: list[str] = args.states
    tcs: list[str] = args.template_configs
    experiment_dir = utils.identify_experiment_dir(
        experiment_name, working_dir=os.getcwd()
    )
    # create any folders that are not in the experiment
    utils.create_experiment_framework(
        experiment_dir,
        necessary_dirs=[
            PP_SCRIPTS_DIR_NAME,
            TEMPLATE_CONFIGS_DIR_NAME,
            STATE_CONFIGS_DIR_NAME,
        ],
    )
    # validate that all necessary folders are in the experiment
    utils.validate_experiment_structure(
        experiment_dir,
        necessary_components=[
            PP_SCRIPTS_DIR_NAME,
            TEMPLATE_CONFIGS_DIR_NAME,
            STATE_CONFIGS_DIR_NAME,
        ],
    )
    # validate the template_configs, moving them to the appropriate spot
    # if they are not there already
    tcs = utils.identify_template_config_paths(
        experiment_dir, TEMPLATE_CONFIGS_DIR_NAME, tcs=tcs
    )
    # load our mapping CSVs
    region_info = pd.read_csv(REGION_INFO_PATH)
    if "all" in states:
        states = list(region_info["stusps"])
    elif "50states" in states:
        states = list(
            region_info.loc[region_info["stid"] == "state", "stusps"]
        )
    elif "hhsregions" in states:
        # stusps is a list of state abr for an hhsregion, so use stname
        # to get the hhs1-hhs10 names
        states = list(
            region_info.loc[region_info["stid"] == "hhsregion", "stname"]
        )
    # empty the STATE_CONFIGS_DIR_NAME directory and refill it with configs
    utils.create_state_subdirectories(
        os.path.join(experiment_dir, STATE_CONFIGS_DIR_NAME),
        state_names=states,
        empty_dir=True,
    )
    # populate each state directory with region specific configs from templates
    utils.populate_config_files(experiment_dir, tcs, region_info)
    print(
        f"{utils.bcolors.OKGREEN}Successfully created and populated state directories{utils.bcolors.ENDC}"
    )
