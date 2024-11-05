# keep imports relative to avoid circular importing
import os

from . import azure_utils
from . import utils as experiment_utils
from .azure_utils import AzureExperimentLauncher

# GLOBALS, DONT CHANGE UNLESS YOU KNOW WHAT YOU ARE DOING
# tells the script where to look for certain files in an experiment
RUNNER_SCRIPT_PATH = "run_task.py"
TEMPLATE_CONFIGS_DIR_NAME = "template_configs"
STATE_CONFIGS_DIR_NAME = "states"
PP_SCRIPTS_DIR_NAME = "postprocessing_scripts"
EXP_DIR_NAME_OPTIONAL = "exp"
PACKAGE_PATH, _ = os.path.split(os.path.realpath(__file__))
FIPS_TO_NAME_PATH = os.path.join(PACKAGE_PATH, "data", "fips_to_name.csv")
POPULATIONS_PATH = os.path.join(PACKAGE_PATH, "data", "CenPop2020_Mean_ST.csv")


# Defines all the different modules able to be imported
__all__ = [
    azure_utils,
    AzureExperimentLauncher,
    experiment_utils,
    RUNNER_SCRIPT_PATH,
    TEMPLATE_CONFIGS_DIR_NAME,
    STATE_CONFIGS_DIR_NAME,
    PP_SCRIPTS_DIR_NAME,
    EXP_DIR_NAME_OPTIONAL,
    FIPS_TO_NAME_PATH,
    POPULATIONS_PATH,
    PACKAGE_PATH,
]
