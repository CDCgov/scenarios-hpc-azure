import json
import os
import shutil

import pandas as pd


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def identify_experiment_dir(experiment_name: str, working_dir: str):
    """Identifies the experiment directory given the current working directory
    and the name of the experiment. Checks the `working_dir` as well as
    `working_dir/exp` for `experiment_name.

    Parameters
    ----------
    experiment_name : str
        name of the experiment, must match the folder name on the users machine
    working_dir : str
        path to the users working area, containing the experiment

    Raises
    ------
    FileNotFoundError
        if unable to find the directory

    Returns
    ------
    str
        directory of the experiment_folder
    """
    experiment_dir = os.path.join(working_dir, experiment_name)
    if not os.path.exists(experiment_dir):
        experiment_dir = os.path.join(working_dir, "exp", experiment_name)
        if not os.path.exists(experiment_dir):
            raise FileNotFoundError(
                "Unable to find your experiment directory within %s, "
                "ensure %s is at the top level or within an exp/ folder"
                % (working_dir, experiment_dir)
            )
    return experiment_dir


def validate_experiment_structure(
    experiment_dir: str, necessary_components: list[str]
):
    """validates `experiment_dir` to ensure it is a valid experiment on which
    the create_experiment script may be run.

    Parameters
    ----------
    experiment_dir : str
        path to the experiment directory
    necessary_components : list[str], optional
        all necessary components of an experiment, including files and
        directories, will check components in order of list.


    Raises
    ------
    FileNotFoundError
        experiment_dir does not exist
    FileNotFoundError
        os.path.join(experiment_dir, component) does not exist for any component
        in necessary_components
    """

    # validate experiment_dir exists
    if not os.path.exists(experiment_dir):
        raise FileNotFoundError(
            "unable to find %s to validate" % experiment_dir
        )
    # validate experiment has all necessary files and directories
    for component in necessary_components:
        if not os.path.exists(os.path.join(experiment_dir, component)):
            raise FileNotFoundError(
                "unable to find %s within %s" % (component, experiment_dir)
            )


def identify_template_config_paths(
    experiment_dir: str, template_configs_dir_name: str, tcs: list[str] | None
) -> list[str]:
    """given a list of template_config paths ensures that each template config
    is found within the appropriate experiment directory
    (experiment_dir/template_configs_dir_name). Copying over template
    configs found elsewhere if necessary.

    Returns a list of paths identifying the correctly placed template configs
    within the experiment folder.

    Parameters
    ----------
    experiment_dir : str
        path to the experiment directory
    template_configs_dir_name : str
        name of the directory meant to hold template configs
    tcs : list[str]
        path to the template_configs provided by the user, may or may not
        be within the experiment

    Returns
    -------
    list[str]
        path to the template configs, possibly relocated to within the
        experiment if they were not within it to begin with.

    Raises
    ------
    FileNotFoundError
        if user does not pass any template configs AND the
        `template_configs_dir_name` directory is empty,
        raises FileNotFoundError
    """

    template_configs_path = os.path.join(
        experiment_dir, template_configs_dir_name
    )
    experiment_name = os.path.basename(experiment_dir)
    if tcs is not None:
        # move all the files into the template_configs_path
        for tc_path in tcs:
            # avoid SameFileError if tc_path == target_path
            if (
                os.path.join(experiment_name, template_configs_dir_name)
                not in tc_path
            ):
                filename = os.path.basename(tc_path)
                target_path = os.path.join(template_configs_path, filename)
                print(
                    f"{bcolors.WARNING}copying {tc_path} to {target_path}{bcolors.ENDC}"
                )
                shutil.copy(tc_path, target_path)
    # files should now be in template_configs folder
    tcs = [
        os.path.join(template_configs_path, f)
        for f in os.listdir(template_configs_path)
        if os.path.isfile(os.path.join(template_configs_path, f))
    ]
    if len(tcs) == 0:
        raise FileNotFoundError(
            "Unable to find any template configs within %s to populate states "
            "you must either specify --template_configs flag or place the "
            "configs within the %s of your experiment"
            % (template_configs_path, template_configs_dir_name)
        )
    return tcs


def create_experiment_framework(
    experiment_dir: str,
    necessary_dirs: list[str] = [
        "postprocessing_scripts",
        "template_configs",
        "states",
    ],
):
    """creates the framework for an experiment, creates intermediate dirs
    if `experiment_dir` is multiple directories long.

    Parameters
    ----------
    experiment_dir : str
        path to where you want the experiment to be
    necessary_dirs : list[str], optional
        directories created to be considered an experiment,
        by default ["postprocessing_scripts", "template_configs", "states"]
    """
    for component in necessary_dirs:
        path = os.path.join(experiment_dir, component)
        if not os.path.exists(path):
            print(
                f"{bcolors.WARNING}creating {path} as it is needed but does not exist in your experiment{bcolors.ENDC}"
            )
            os.makedirs(path, exist_ok=True)


def create_state_subdirectories(dir: str, state_names: list[str]):
    """
    function to create an experiment directory `dir` and then create
    subfolders for each Postal Abreviation in `state_names`.
    Will not override if `dir` or `dir/state_names[i]` already exists

    Parameters
    ------------
    `dir`: str
        relative or absolute directory path of the experiment's state folder,
        for which subdirectories per state will be created under it.
    `state_names`: list[str]
        list of USPS postal codes per state involved in the experiment, will create subfolders of `dir`
        with each code.

    Returns
    ------------
    None
    """
    # Create the main directory if it does not exist
    if not os.path.exists(dir):
        os.makedirs(dir)
    print(
        f"{bcolors.WARNING}removing and repopulating regions within {dir}{bcolors.ENDC}"
    )
    # Create subdirectories for each state inside the "states" folder
    for state in state_names:
        state_dir = os.path.join(dir, state)
        if os.path.exists(state_dir):
            os.rmdir(state_dir)
        os.makedirs(state_dir)


def populate_config_files(
    dir: str, configs: list[str], region_info: pd.DataFrame
):
    """
    scans an experiment directory `dir` opening each folder, and copying over read-only versions
    of each json file in `configs`, modifying the "REGIONS" key to match the postal code.
    Modifies the `POP_SIZE` variable to match the states population according to the census.
    Modifies the `INITIAL_INFECTIONS` variable to equal the same % of the population as in the template config.
        eg: 2% of TOTAL_POP in template config applied to each state's individual `POP_SIZE`

    will raise an error if a subdirectory of `dir` is not a postal code able to be looked up.

    Parameters
    ------------
    `dir`: str
        relative or absolute directory path of the experiment,
        contains subdirectories created by `create_state_subdirectories`

    `configs`: list[str]
        list of paths to each config template, these config templates will be copied into each subdirectory as read-only
        they will have their "REGIONS" key changed to resemble the state the subdirectory is modeling.

    `region_info`: pd.DataFrame
        dataframe containing "stusps", "stname", and population
        columns to map regions to their usps codes and populations

    Returns
    ------------
    None
    """
    dir = os.path.join(dir, "states")
    for subdir in os.listdir(dir):
        subdir_path = os.path.join(dir, subdir)
        if os.path.isdir(subdir_path):
            state_name = code_to_state(subdir, region_info)
            state_pop = code_to_pop(state_name, region_info)

            for config_file_path in configs:
                # Read the original JSON file
                with open(config_file_path) as f:
                    state_config = json.load(f)

                # Change the "REGION" key to state name
                state_config["REGIONS"] = [state_name]

                if "POP_SIZE" in state_config.keys():
                    # havent changed yet, so old value still in `state_config`
                    template_pop_size = state_config["POP_SIZE"]
                    # match the same % of the population as in the template config to new state POP_SIZE
                    if "INITIAL_INFECTIONS" in state_config.keys():
                        template_initial_inf = state_config[
                            "INITIAL_INFECTIONS"
                        ]
                        # state_pop * (% of infections in the template config)
                        # round to 3 sig figs, convert to int
                        state_config["INITIAL_INFECTIONS"] = int(
                            float(
                                "%.3g"
                                % (
                                    state_pop
                                    * (
                                        template_initial_inf
                                        / template_pop_size
                                    )
                                )
                            )
                        )
                    # round pop sizes 3 sig figs then convert to int
                    state_config["POP_SIZE"] = int(float("%.3g" % state_pop))

                # Create a new read-only copy of the JSON file with modified data
                new_config_file_path = os.path.join(
                    subdir_path, os.path.basename(config_file_path)
                )
                # if the config file already exists, we remove and override it.
                if os.path.exists(new_config_file_path):
                    # change back from readonly so it can be deleted, otherwise get PermissionError
                    os.chmod(new_config_file_path, 0o777)
                    os.remove(new_config_file_path)

                with open(new_config_file_path, "w") as f:
                    json.dump(state_config, f, indent=4)

                # Set the new file permissions to read-only
                os.chmod(new_config_file_path, 0o444)


def code_to_state(code: str, state_names_map: pd.DataFrame):
    """
    basic function to read in an postal code and return associated state name

    Parameters
    ----------
    code: str
        usps code the state
    state_names_map: pd.DataFrame
        dataframe containing "stusps" and "stname"
        columns to map states to their usps codes

    Returns
    ----------
    str/KeyError: state name, or KeyError if code does not point to a state or isnt an str
    """
    state_info = state_names_map[state_names_map["stusps"] == code]
    if len(state_info) == 1:
        return state_info["stname"].iloc[0]
    else:
        raise KeyError("Unknown code %s" % code)


def code_to_pop(state_name: str, state_pops_map: pd.DataFrame):
    """
    basic function to read in an postal code and return associated state name

    Parameters
    ----------
    state_name: str
        state name
    state_pops_map: pd.DataFrame
        dataframe containing mapping from `STNAME` to `POPULATION`

    Returns
    ----------
    str/KeyError: state population, or KeyError if invalid state name
    """
    state_pop = state_pops_map[state_pops_map["stname"] == state_name]
    if len(state_pop) == 1:
        return state_pop["population"].iloc[0]
    else:
        raise KeyError(
            "unable to find population for state name %s" % state_name
        )
