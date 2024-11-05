# keep imports relative to avoid circular importing
import os

from . import azure_utils
from . import utils as experiment_utils
from .azure_utils import AzureExperimentLauncher

# GLOBALS, DONT CHANGE UNLESS YOU KNOW WHAT YOU ARE DOING
# tells the script where to look for certain files in an experiment
# runner script filename
RUNNER_SCRIPT_PATH = "run_task.py"
# where experiment stores template configs
TEMPLATE_CONFIGS_DIR_NAME = "template_configs"
# where experiment stores state-specific config files
STATE_CONFIGS_DIR_NAME = "states"
# where experiment stores postprocessing scripts
PP_SCRIPTS_DIR_NAME = "postprocessing_scripts"
# where experiments are stored. subfolders of this dir are experiment_names
EXP_DIR_NAME = "exp"
# path from user's CWD to where their azure configuration toml is stored
SECRETS_DIR_NAME = "secrets"
SECRETS_FILE_NAME = "configuration_cfaazurebatchprd.toml"
# path to this package on users machine
PACKAGE_PATH, _ = os.path.split(os.path.realpath(__file__))
# path to the regions mapping csv generated from raw data
REGION_INFO_PATH = os.path.join(
    PACKAGE_PATH, "data", "regions_mapping_combined.csv"
)


# Defines all the different modules able to be imported
__all__ = [
    azure_utils,
    AzureExperimentLauncher,
    experiment_utils,
    RUNNER_SCRIPT_PATH,
    TEMPLATE_CONFIGS_DIR_NAME,
    STATE_CONFIGS_DIR_NAME,
    PP_SCRIPTS_DIR_NAME,
    EXP_DIR_NAME,
    PACKAGE_PATH,
    REGION_INFO_PATH,
]
