import argparse
import os

import pandas as pd

from . import (
    FIPS_TO_NAME_PATH,
    POPULATIONS_PATH,
    PP_SCRIPTS_DIR_NAME,
    STATE_CONFIGS_DIR_NAME,
    TEMPLATE_CONFIGS_DIR_NAME,
    utils,
)

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
    state_names_map = pd.read_csv(FIPS_TO_NAME_PATH)
    state_pops_map = pd.read_csv(POPULATIONS_PATH)
    # adding a USA row with the sum of all state pops
    usa_pop_row = pd.DataFrame(
        [
            [
                "US",
                "United States",
                sum(state_pops_map["POPULATION"]),
                "+44.582076",  # latitude
                "+103.461760",  # longitude
            ]
        ],
        columns=state_pops_map.columns,
    )
    state_pops_map = pd.concat(
        [state_pops_map, usa_pop_row], ignore_index=True
    )
    if "all" in states:
        states = list(state_names_map["stusps"])
    utils.create_state_subdirectories(
        os.path.join(experiment_dir, STATE_CONFIGS_DIR_NAME),
        state_names=states,
    )
    utils.populate_config_files(
        experiment_dir, tcs, state_names_map, state_pops_map
    )
    print(
        f"{utils.bcolors.OKGREEN}Successfully created and populated state directories{utils.bcolors.ENDC}"
    )
