#!/bin/bash
# identify the directory this setup script is in
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LAUNCH_EXPERIMENT_FILENAME="launch_experiment"
CREATE_EXPERIMENT_FILENAME="create_experiment"
SECRETS_TOML_FILENAME="configuration_cfaazurebatchprd.toml"
SECRETS_DIR="$SCRIPT_DIR/secrets/$SECRETS_TOML_FILENAME"
RESTART_SHELL=false
ERRORS_AROSE=false
# colors for errors, changes, and reminders
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
if [ ! -f "$SECRETS_DIR" ]; then
    printf "${RED}ERROR:${NC} $SECRETS_DIR DOES NOT EXIST, GET AZURE CONFIG TOML FROM A MANAGER \n"
    ERRORS_AROSE=true
fi

# identify the launcher executable location, then make sure its able to
# be executed and add it to $PATH if necessary
LAUNCH_EXPERIMENT_DIR="$SCRIPT_DIR/src/scenarios_hpc_azure"
LAUNCH_EXPERIMENT_FILE_PATH="$LAUNCH_EXPERIMENT_DIR/$LAUNCH_EXPERIMENT_FILENAME"

# Check if LAUNCH_EXPERIMENT_DIR exists and is a regular file
if [ -f "$LAUNCH_EXPERIMENT_FILE_PATH" ]; then
    # Check if LAUNCH_EXPERIMENT_DIR is not executable
    if [ ! -x "$LAUNCH_EXPERIMENT_FILE_PATH" ]; then
        # Make LAUNCH_EXPERIMENT_FILENAME executable for the user who owns it
        chmod u+x "$LAUNCH_EXPERIMENT_FILE_PATH"
        printf "${GREEN}CHANGE:${NC} Made $LAUNCH_EXPERIMENT_FILE_PATH executable.\n"
    fi
    # Add this directory to PATH in .bashrc if it's not already there
    if ! grep -q "export PATH=\"$LAUNCH_EXPERIMENT_DIR:\$PATH\"" ~/.bashrc; then
        echo "export PATH=\"$LAUNCH_EXPERIMENT_DIR:\$PATH\"" >> ~/.bashrc
        printf "${GREEN}CHANGE:${NC} added $LAUNCH_EXPERIMENT_DIR to path\n"
        RESTART_SHELL=true
    fi
else
    printf "${RED}ERROR:${NC} $CREATE_EXPERIMENT_FILE_PATH does not exist or is not a regular file. \n"
    ERRORS_AROSE=true
fi

# now do the same thing but for the experiment creator scripts
CREATE_EXPERIMENT_DIR="$SCRIPT_DIR/src/scenarios_hpc_azure"
CREATE_EXPERIMENT_FILE_PATH="$CREATE_EXPERIMENT_DIR/$LAUNCH_EXPERIMENT_FILENAME"

# Check if CREATE_EXPERIMENT_FILE_PATH exists and is a regular file
if [ -f "$CREATE_EXPERIMENT_FILE_PATH" ]; then
    # Check if CREATE_EXPERIMENT_FILE_PATH is not executable
    if [ ! -x "$CREATE_EXPERIMENT_FILE_PATH" ]; then
        # Make execute.sh executable for the user who owns it
        chmod u+x "$CREATE_EXPERIMENT_FILE_PATH"
        echo "Made $CREATE_EXPERIMENT_FILE_PATH executable."
    fi
    if ! grep -q "export PATH=\"$CREATE_EXPERIMENT_DIR:\$PATH\"" ~/.bashrc; then
        echo "export PATH=\"$CREATE_EXPERIMENT_DIR:\$PATH\"" >> ~/.bashrc
        printf "${GREEN}CHANGE:${NC} added $CREATE_EXPERIMENT_DIR to path\n"
        RESTART_SHELL=true
    fi
else
    printf "${RED}ERROR:${NC} $CREATE_EXPERIMENT_FILE_PATH does not exist or is not a regular file. \n"
    ERRORS_AROSE=true
fi

# if RESTART_SHELL then print a reminder to the user to restart shell
if [ "$RESTART_SHELL" == "true" ]; then
    printf "${YELLOW}changes were made, please restart your terminal or run 'source ~/.bashrc' to apply changes.${NC} \n"
fi
# if we did not have any errors, we can display something to the user
# so they know the program ran
if  [ "$ERRORS_AROSE" = "false" ]; then
    printf "${GREEN}Setup finished without errors!${NC} \n"
fi


