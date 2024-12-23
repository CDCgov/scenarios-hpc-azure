import copy
import json
import math
import os
from typing import Iterable, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects

# import plotly.graph_objs as go
import seaborn as sns
from cfa_azure.clients import AzureClient
from dynode import vis_utils
from dynode.config import distribution_converter
from matplotlib.colors import LinearSegmentedColormap
from plotly.subplots import make_subplots
from scipy.stats import pearsonr
from tqdm import tqdm

from ..azure_utils import download_directory_from_azure


class Node:
    # a helper class to store directories in a tree
    def __init__(self, name):
        self.name = name
        self.subdirs = {}


def construct_tree(file_paths: Iterable[str], root=None) -> Node:
    """given a iterable of strings, constructs a tree of directories from root "/".
    Used to efficiently traverse directories after tree is constructed.
    leaf nodes are files with a "." like .txt or .json

    Parameters
    ----------
    file_paths : Iterable[str]
        a list or iterable containing file paths, each file path may not begin with "/"
        any directories or paths of directories with no files at the end will be skipped.

    Returns
    -------
    Node
        A node object containing a dictionary of subdirectories, files have a `name` field but
        an empty dictionary of subdirs.
    """
    if not isinstance(root, Node):
        root = Node("/")
    for path in tqdm(file_paths, desc="Building Azure Tree Structure"):
        # indicates this is an actual file like .txt or .json or .out
        if "." in path:
            directories, filename = path.rsplit("/", 1)
            current_node = root
            # experiment/jobid/state minimum depth 3
            if len(directories.split("/")) >= 3:
                for directory in directories.split("/"):
                    if directory not in current_node.subdirs:
                        current_node.subdirs[directory] = Node(directory)
                    current_node = current_node.subdirs[directory]
                current_node.subdirs[filename] = Node(filename)
    return root


def append_local_projects_to_tree(local_cache_path, root):
    """takes a Node and appends all new paths from `os.path.walk(local_cache_path)` onto `root`

    Parameters
    ----------
    local_cache_path : str
        path to the local cache, which contains directories in the `exp/job/state/*` format
    root: Node
        the tree root node on which you append paths onto.

    Returns
    -------
    Node
        the node `root` potentially with new subdirs within, or unchanged if
        all paths within local_cache_path match those already in `root` before the call.
    """
    # we are spoofing azures list_blobs function to pass our local files into the tree as well
    file_paths = []
    for path, _, files in os.walk(local_cache_path):
        # if non-empty we have reached the leaf nodes
        for file in files:
            # go through each leaf node, remove the prepending `local_cache_path`
            # from the path, and add on the file name to the end
            file_paths.append(
                (path + "/" + file).replace(local_cache_path + "/", "")
            )
    appended_root = construct_tree(file_paths, root)
    return appended_root


def get_azure_files(
    exp: str,
    jobid: str,
    states: list[str],
    scenario: str,
    azure_client: AzureClient,
    local_cache_path: str,
) -> str:
    """Reads in all files from the output blob `exp/jobid/state` in `azure_client.out_cont_client`
    and stores them in the `shiny_cache` directory.
    If the cache path already exists for that run (even if it is empty!), nothing is downloaded.

    Raises ValueError error if `exp/jobid/state/` does not exist in the output blob

    Parameters
    ----------
    exp : str
        experiment name
    jobid : str
        jobid name
    state : list[str]
        list of usps postal code of each state requested
    scenario : str
        optional scenario, N/A if not applicable to the directory structure
    azure_client : cfa_azure.AzureClient
        Azure client to access azure blob storage and download the files
    local_cache_path: str
        the path to the local cache where files are stored
    Returns
    -------
    list[str]
        paths into which files were loaded (if they did not already exist there)
    """
    azure_state_paths = []
    for state in states:
        azure_blob_path = os.path.join(exp, jobid, state)
        if scenario != "N/A":  # if visualizing a scenario append to the path
            azure_blob_path = os.path.join(azure_blob_path, scenario)
        azure_blob_path = azure_blob_path.replace("\\", "/") + "/"
        azure_state_paths.append(azure_blob_path)
    return_paths = download_directory_from_azure(
        azure_client, azure_state_paths, local_cache_path, overwrite=False
    )
    return return_paths


def get_population_sizes(
    states: tuple[str],
    state_name_lookup: pd.DataFrame,
    state_pop_lookup: pd.DataFrame,
):
    """loads population CSVs and returns the population size of each state

    Parameters
    ----------
    states : tuple[str]
        tuple of each state as a USPS postal code
    demographic_data_path : str
        path to the directory containing age distribution and pop count csvs
    """
    states = [
        state_name_lookup[state_name_lookup["stusps"] == state]["stname"].iloc[
            0
        ]
        for state in states
    ]
    pop_sizes = []
    for state_name in states:
        state_pop = state_pop_lookup[state_pop_lookup["STNAME"] == state_name]
        pop_sizes.append(state_pop["POPULATION"].iloc[0])
    return pop_sizes


def flatten_list_parameters(
    samples: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    given a dictionary of parameter names and samples, identifies any parameters that are
    placed under a single name, but actually multiple independent draws from the same distribution.
    These parameters are often the result of a call to `numpyro.plate(P)` for some number of draws `P`
    After identifying plated samples, this function will separate the `P` draws into their own
    keys in the samples dictionary.

    Parameters
    ----------
    `samples`: dict{str: np.ndarray}
        a dictionary where parameter names are keys and samples are a list.
        In the case of M chains and N samples per chain, the list will be of shape MxN normally
        with one row per chain, each containing N samples.
        In the case that the parameter is drawn P independent times, the list will be of shape
        MxNxP.

    Returns
    ----------
    dict{str: np.ndarray}  a dictionary in which parameters with lists of shape MxNxP are split into
    P separate parameters, each with lists of shape MxN for M chains and N samples.
    This function scaled with any number of dimensions > 2. So for PxQ independent draws
    will be separated into PxQ parameters each with lists of shape MxN.

    NOTE
    -----------
    If you only have parameters of dimension 2, nothing will be changed and a copy of your dict will be returned
    """
    return_dict = {}
    for key, value in samples.items():
        if isinstance(value, np.ndarray) and value.ndim > 2:
            num_dims = value.ndim - 2
            indices = (
                np.indices(value.shape[-num_dims:]).reshape(num_dims, -1).T
            )

            for idx in indices:
                new_key = f"{key}"
                for i in range(len(idx)):
                    new_key += f"_{idx[i]}"

                new_value = value[
                    tuple([slice(None)] * (value.ndim - num_dims) + list(idx))
                ]
                return_dict[new_key] = new_value
        else:
            return_dict[key] = value
    return return_dict


def drop_keys_with_substring(dct: dict[str], drop_s: str):
    """A simple helper function designed to drop keys from a dictionary if they contain some substring

    Parameters
    ----------
    dct : dict[str, Any]
        a dictionary with string keys
    drop_s : str
        keys containing `drop_s` as a substring will be dropped

    Returns
    -------
    dict[str, any]
        dct with keys containing drop_s removed, otherwise untouched.
    """
    keys_to_drop = [key for key in dct.keys() if drop_s in key]
    for key in keys_to_drop:
        del dct[key]
    return dct


def prepare_posterior_data(
    posteriors: dict[str, list],
    flatten_chains=False,
    drop_timesteps=True,
):
    """A helper function used to prepare posterior sample data for visualization
    will scan for parameters generated via `numpyro.plate` and separate
    those lists into _i parameters where i is the index of the plated list.

    Also is able to optionally flatten chains / samples into a 1d numpy array

    Can drop the `timestep_s/e/i/c` posteriors before performing these
    operations in case they were included (this is mostly a problem for
    old experiments before separation of these files occurred.)

    Parameters
    ----------
    posteriors : dict[str: list]
        input posteriors with parameter name as the key and the
        chain/val as a 2d matrix. Will flatten 3+ dimensional matricies.
    flatten_chains : bool, optional
        whether or not to convert to numpy array and flatten
        chains/samples together into a 1d array, by default False
    drop_timesteps : bool, optional
        whether to drop any `timesteps_` parameters before
        performing operations, by default True

    Returns
    -------
    dict[str: list|np.ndarray]
        posteriors with operations applied
    """
    if drop_timesteps:
        # drop any timestep variables if they exist within the posteriors
        posteriors = drop_keys_with_substring(posteriors, "timestep")
    posteriors: dict[str, list] = flatten_list_parameters(posteriors)
    if flatten_chains:
        posteriors = {
            key: np.array(matrix).flatten()
            for key, matrix in posteriors.items()
        }
    return posteriors


def _create_figure_from_timeline(
    timeline: pd.DataFrame,
    plot_name: str,
    x_axis: str,
    y_axis: Union[str, list[str]],
    plot_type: str,
    group_by: str = None,
) -> plotly.graph_objs.Figure:
    """
    PRIVATE FUNCTION
    plots a line plot given a pandas dataframe and some x/y axis to plot and group bys.
    Formats this figure according to the plot_type title passed.
    By default traces that belong to grouped categories in `group_by` are all marked
    with a "remove_duplicate" in their name attribute, except the first of the group.
    This is useful for only exposing 1 group to the legend instead of all four.
    By default legends and hover tool tips are disabled for all traces

    Parameters
    ----------
    timeline : pd.DataFrame
        dataframe containing data to plot
    plot_name : str
        plot title
    x_axis : str
        title of the column which will serve as the x axis, usually "date"
    y_axis : Union[str, list[str]]
        title or titles of the columns to be plotted as y axis
    plot_type : str
        the generic name of the plot, if multiple y_axis names are provided,
        the diff of each y_axis name from the `plot_type` is used to identify each line
    group_by : str, optional
        a column name on which to group by, by default None

    Returns
    -------
    plotly.graph_objs.Figure
        figure used to append traces
    """
    # we use plotly express since it has the `line_group` param
    line = px.line(
        timeline,
        x=x_axis,
        y=y_axis,
        title=plot_name,
        labels=y_axis,
        line_group=group_by,
    )
    groups = len(timeline[group_by].unique()) if group_by else 1
    for i, data in enumerate(line.data, 0):
        # if we pass a list of y_axis, we provide labels only for what
        # differs from label to label, this aids in readability
        if data.name == plot_type:
            new_name = data.name.replace("_", " ")
        else:
            new_name = data.name.replace(plot_type, "").replace("_", "-")
        # we want to remove duplicate legend entries, so we mark duplicates in the name
        data.name = new_name + (
            "" if (i % groups == 0) or (i == 0) else "remove_duplicate"
        )
        # by default we disable hover tooltips,
        # we will enable them later for select lines only
        data.hoverinfo = "none"
        data.hovertemplate = None
        data.showlegend = False
    return line


def load_checkpoint_inference_chains(
    cache_path,
    overview_subplot_width: int,
    overview_subplot_height: int,
) -> plotly.graph_objs.Figure:
    """
    Given a path a folder containing downloaded azure files, checks for the existence
    of the checkpoint.json file, if it exists, returns a figure plotting
    the inference chains of each of the sampled parameters, raises a FileNotFoundError if csv
    is not found within `cache_path`

    Parameters
    ----------
    cache_path : str
        path to the local path on machine with files within.
    subplot_width: int
        integer representing pixel width of each subplot in the overview
    subplot_height: int
        integer representing pixel height of each subplot in the overview

    Returns
    -------
    Figure
        plotly Figure with each of the sampled parameters as its own line plot
    """
    checkpoint_path = os.path.join(cache_path, "checkpoint.json")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            "attempted to visualize an inference chain without an `checkpoint.json` file"
        )
    posteriors = json.load(open(checkpoint_path, "r"))
    # any sampled parameters created via numpyro.plate will mess up the data
    # flatten plated parameters into separate keys
    posteriors = prepare_posterior_data(posteriors, drop_timesteps=True)
    num_sampled_parameters = len(posteriors.keys())
    # we want a mostly square subplot, so lets sqrt and take floor/ceil to deal with odd numbers
    num_rows = math.isqrt(num_sampled_parameters)
    num_cols = math.ceil(num_sampled_parameters / num_rows)
    # we will title these subplots and make sure to leave blank titles in case of odd numbers
    subplot_titles_padded = list(posteriors.keys()) + [""] * (
        num_rows * num_cols - num_sampled_parameters
    )
    fig = make_subplots(
        num_rows,
        num_cols,
        horizontal_spacing=0.01,
        vertical_spacing=0.08,
        subplot_titles=subplot_titles_padded,
    )
    for i, particles in enumerate(posteriors.values()):
        particles = np.array(particles)
        row = int(i / num_cols) + 1
        col = i % num_cols + 1
        num_chains = particles.shape[0]
        columns = ["chain_%s" % chain for chain in range(num_chains)]
        # right now particles.shape = (chain, sample), transpose so columns are our chain num
        df = pd.DataFrame(particles.transpose(), columns=columns)
        traces = px.line(df, y=columns)["data"]
        fig.add_traces(
            traces,
            rows=row,
            cols=col,
        )
    fig.update_layout(
        width=overview_subplot_width * num_cols + 50,
        height=overview_subplot_height * num_rows + 50,
        title_text="",
        legend_tracegroupgap=0,
        hovermode=False,
    )
    # only keep one copy of the legend since they all the same
    fig.update_traces(showlegend=False)
    fig.update_traces(showlegend=True, row=1, col=1)
    return fig


def load_prior_distributions_plot(cache_path, matplotlib_theme):
    state = cache_path.split("/")[-2]
    priors_path = os.path.join(cache_path, "config_inferer_used.json")
    posteriors_path = os.path.join(cache_path, "checkpoint.json")
    if os.path.exists(priors_path):
        # read the config file, transform all distributions into
        # numpyro distribution objects so they may be sampled and displayed
        config_json_str = open(priors_path).read()
        config = json.loads(
            config_json_str, object_hook=distribution_converter
        )
        styles = ["seaborn-v0_8-colorblind", matplotlib_theme]
        hist_kwargs = copy.copy(
            vis_utils.plot_prior_distributions.__defaults__[2]
        )
        median_line_kwargs = copy.copy(
            vis_utils.plot_prior_distributions.__defaults__[3]
        )
        if os.path.exists(posteriors_path):
            # if we will eventually be overlaying posteriors, we will need
            # our plot labels to differ the priors vs posteriors
            hist_kwargs["label"] = "priors"
            hist_kwargs["color"] = "#046b99"
            hist_kwargs["alpha"] = 0.5
            median_line_kwargs["color"] = "#046b99"
        fig = vis_utils.plot_prior_distributions(
            config,
            matplotlib_style=styles,
            hist_kwargs=hist_kwargs,
            median_line_kwargs=median_line_kwargs,
        )
        if os.path.exists(posteriors_path):
            print("overlaying posteriors onto axis object")
            # overlay the posteriors onto the priors if they exist
            posteriors = json.load(open(posteriors_path))
            posteriors = prepare_posterior_data(
                posteriors, flatten_chains=True, drop_timesteps=True
            )
            # going to need the axis objects back to modify them
            axs = fig.get_axes()
            for param_name in posteriors:
                # search the correct axis object to modify
                ax = next(
                    (ax for ax in axs if ax.get_title() == param_name), None
                )
                # sometimes parameters not in the config are sampled, ignore those
                if ax is not None:
                    ax.hist(
                        posteriors[param_name],
                        label="posteriors",
                        alpha=0.5,
                        color="#2e8540",
                        **vis_utils.plot_prior_distributions.__defaults__[2],
                    )
                    ax.axvline(
                        np.median(posteriors[param_name]),
                        linestyle="dotted",
                        linewidth=3,
                        label="posterior median",
                        color="#2e8540",
                    )
                    valid_ax = ax
                    # save the last valid axis object to produce a legend with
            # remove previous legend and replace it with updated one
            fig.legends[0].remove()
            handles, labels = valid_ax.get_legend_handles_labels()
            fig.legend(handles, labels, loc="outside upper right", ncols=2)
            fig.suptitle("priors and posteriors visualized: %s" % state)

    else:
        raise FileNotFoundError(
            "%s does not exist, either the experiment did "
            "not save a config used or loading files failed" % priors_path
        )
    return fig


def load_checkpoint_inference_correlations(
    cache_path,
    overview_subplot_size: int,
) -> plotly.graph_objs.Figure:
    """Given a path a folder containing downloaded azure files, checks for the existence
    of the checkpoint.json file, if it exists, returns a figure plotting
    the correlation of each sampled parameter with all other sampled parameters

    Parameters
    ----------
    cache_path : str
        path to the local path on machine with files within.
    overview_subplot_size: int
        the side of the width/height of the correlation matrix in pixels

    Returns
    -------
    Figure
        plotly Figure with `n` rows and `n` columns where `n` is the number of sampled parameters
    """
    checkpoint_path = os.path.join(cache_path, "checkpoint.json")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            "attempted to visualize an inference correlation without an `checkpoint.json` file"
        )
    posteriors = json.load(open(checkpoint_path, "r"))
    # flatten all the data into 1d and drop the final timesteps posteriors
    posteriors = prepare_posterior_data(
        posteriors, flatten_chains=True, drop_timesteps=True
    )
    # Compute the correlation matrix, reverse it so diagonal starts @ top left
    correlation_matrix = pd.DataFrame(posteriors).corr()[::-1]

    # Create a heatmap of the correlation matrix
    fig = plotly.graph_objects.Figure(
        plotly.graph_objects.Heatmap(
            x=correlation_matrix.columns,
            y=correlation_matrix.index,
            z=np.array(correlation_matrix),
            text=correlation_matrix.values,
            texttemplate="%{text:.2f}",
            # colorscale="RdBu_r",
            colorscale="Blues",
        )
    )
    # do some small style choices
    fig.update_layout(
        width=overview_subplot_size + 50,
        height=overview_subplot_size + 50,
        title_text="",
        legend_tracegroupgap=0,
        # hovermode=False,
    )
    return fig


def load_checkpoint_inference_violin_plots(
    cache_path,
    matplotlib_theme: str,
) -> plotly.graph_objs.Figure:
    """Given a path a folder containing downloaded azure files, checks for the existence
    of the checkpoint.json file, if it exists, returns a figure of one violin plot per
    sampled parameter describing the distribution of sampled values.

    Parameters
    ----------
    cache_path : str
        path to the local path on machine with files within.

    Returns
    -------
    Figure
        plotly Figure with each of the sampled parameters as its own violin plot
    """
    checkpoint_path = os.path.join(cache_path, "checkpoint.json")
    priors_path = os.path.join(cache_path, "config_inferer_used.json")
    state = cache_path.split("/")[-2]
    if not os.path.exists(checkpoint_path) and not os.path.exists(priors_path):
        raise FileNotFoundError(
            "attempted to visualize violin plots without priors or posteriors"
        )
    posteriors = None
    priors = None
    if os.path.exists(checkpoint_path):
        posteriors = json.load(open(checkpoint_path, "r"))
        # flatten any usage of numpyro.plate into separate parameters,
        # otherwise youll get nonsense in the next step
        posteriors = prepare_posterior_data(
            posteriors, flatten_chains=True, drop_timesteps=True
        )
    if os.path.exists(priors_path):
        priors = json.load(
            open(priors_path, "r"), object_hook=distribution_converter
        )
        priors = vis_utils._sample_prior_distributions(priors, 5000)
    styles = ["seaborn-v0_8-colorblind", matplotlib_theme]

    fig = vis_utils.plot_violin_plots(
        priors=priors, posteriors=posteriors, matplotlib_style=styles
    )
    fig.suptitle("Violin Plot of Parameters : %s" % state)
    return fig


def load_checkpoint_inference_correlation_pairs(
    cache_path,
    overview_subplot_size: int,
):
    """Given a path a folder containing downloaded azure files, checks for the existence
    of the checkpoint.json file, if it exists, returns a figure plotting
    the correlation of each sampled parameter with all other sampled parameters
    on the upper half of the plot the correlation values, on the diagonal a
    historgram of the posterior values, and on the bottom half a scatter
    plot of the parameters against eachother.


    Parameters
    ----------
    cache_path : str
        path to the local path on machine with files within.
    overview_subplot_size: int
        the side of the width/height of the correlation matrix in pixels

    Returns
    -------
    Figure
        plotly Figure with `n` rows and `n` columns where `n` is the number of sampled parameters
    """
    checkpoint_path = os.path.join(cache_path, "checkpoint.json")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            "attempted to visualize an inference correlation without an `checkpoint.json` file"
        )
    posteriors = json.load(open(checkpoint_path, "r"))
    posteriors = prepare_posterior_data(
        posteriors, flatten_chains=False, drop_timesteps=True
    )
    # convert lists to np.arrays
    posteriors = {
        key: np.array(val) if isinstance(val, list) else val
        for key, val in posteriors.items()
    }
    # pick first key, get the samples for that key, get the shape of that np.ndarray
    number_of_samples = posteriors[list(posteriors.keys())[0]].shape[1]
    # if we are dealing with many samples per chain, narrow down to 100 samples per chain
    if number_of_samples > 250:
        selected_indices = np.random.choice(
            number_of_samples, size=100, replace=False
        )
        posteriors = {
            key: matrix[:, selected_indices]
            for key, matrix in posteriors.items()
        }
    number_of_samples = posteriors[list(posteriors.keys())[0]].shape[1]
    # Flatten matrices including chains and create Correlation DataFrame
    posteriors = {
        key: np.array(matrix).flatten() for key, matrix in posteriors.items()
    }
    columns = posteriors.keys()
    num_cols = len(list(columns))
    label_size = max(2, min(10, 200 / num_cols))
    # Compute the correlation matrix, reverse it so diagonal starts @ top left
    samples_df = pd.DataFrame(posteriors)
    # correlation_matrix = samples_df.corr()
    cmap = LinearSegmentedColormap.from_list("", ["red", "grey", "blue"])

    def reg_coef(x, y, label=None, color=None, **kwargs):
        ax = plt.gca()
        r, p = pearsonr(x, y)
        ax.annotate(
            "{:.2f}".format(r),
            xy=(0.5, 0.5),
            xycoords="axes fraction",
            ha="center",
            # vary size and color by the magnitude of correlation
            color=cmap(r),
            size=label_size * abs(r) + label_size,
        )
        # ax.texts[0].set_size(16)
        ax.set_axis_off()

    def reg_plot_custom(x, y, label=None, color=None, **kwargs):
        ax = plt.gca()
        r, p = pearsonr(x, y)
        ax = sns.regplot(
            x=x,
            y=y,
            ax=ax,
            fit_reg=True,
            scatter_kws={"alpha": 0.2, "s": 0.5},
            line_kws={"color": cmap(r), "linewidth": 1},
        )

    # Create the plot
    g = sns.PairGrid(
        data=samples_df,
        vars=columns,
        height=5,
        diag_sharey=False,
        layout_pad=0.01,
    )
    # g.figure.set_size_inches((num_cols + 1, num_cols + 1))
    # g.figure.tight_layout()
    g.map_upper(reg_coef)
    g = g.map_lower(
        reg_plot_custom,  # fit_reg=True  # scatter_kws={"edgecolor": "white"}
    )
    g = g.map_diag(sns.histplot, kde=True)
    for ax in g.axes.flatten():
        plt.setp(ax.get_xticklabels(), rotation=45, size=label_size)
        plt.setp(ax.get_yticklabels(), rotation=45, size=label_size)
        # extract the existing xaxis label
        xlabel = ax.get_xlabel()
        # set the xaxis label with rotation
        ax.set_xlabel(xlabel, size=label_size, rotation=90, labelpad=4.0)

        ylabel = ax.get_ylabel()
        ax.set_ylabel(ylabel, size=label_size, rotation=0, labelpad=15.0)
        ax.label_outer(remove_inner_ticks=True)
    # Adjust layout to make sure everything fits
    px = 1 / plt.rcParams["figure.dpi"]
    g.figure.set_size_inches((1600 * px, 1600 * px))
    g.figure.tight_layout(pad=0.01, h_pad=0.01, w_pad=0.01)

    # Adjust spacing if necessary (values are fractions of figure size)
    # g.figure.subplots_adjust(
    #     left=0.08, right=0.92, top=0.92, bottom=0.08, wspace=0.1, hspace=0.1
    # )
    g.figure.subplots_adjust(wspace=0.1, hspace=0.1)
    g.figure.savefig("testing_corr2.png")
    return g.figure


def _generate_row_wise_legends(fig, num_cols):
    # here we are setting up one legend per row, it is messy bc plotly does not
    # usually allow for subplot row legends so we have to go through
    # each yaxis in the whole plot and do it this way
    for i, yaxis in enumerate(fig.select_yaxes()):
        # ruw and col values in plotly start at 1...
        row_num = int(i / num_cols) + 1
        legend_name = f"legend{row_num}"
        # we only want to do this operation once per row, thus % == 0
        if i % num_cols == 0:
            fig.update_layout(
                {legend_name: dict(y=yaxis.domain[1], yanchor="top")},
                showlegend=True,
            )
            # applys over all columns in this row
            fig.update_traces(
                row=row_num,
                legend=legend_name,
            )


def _cleanup_and_normalize_timelines(
    all_state_timelines,
    day_fidelity,
    plot_types,
    plot_normalizations,
    states,
    state_pop_sizes,
):
    # Select columns with 'float64' dtype
    float_cols = list(all_state_timelines.select_dtypes(include="float64"))
    # round down near-zero values to zero to make plots cleaner
    all_state_timelines[float_cols] = all_state_timelines[float_cols].mask(
        np.isclose(all_state_timelines[float_cols], 0, atol=1e-4), 0
    )
    for plot_type, plot_normalization in zip(plot_types, plot_normalizations):
        for state_name, state_pop in zip(states, state_pop_sizes):
            # if normalization is set to 1, we dont normalize at all.
            normalization_factor = (
                plot_normalization / state_pop
                if plot_normalization > 1
                else 1.0
            )
            # select all columns from that column type
            cols = [
                col for col in all_state_timelines.columns if plot_type in col
            ]
            # update that states columns by the normalization factor chosen for that column
            all_state_timelines.loc[
                all_state_timelines["state"] == state_name,
                cols,
            ] *= normalization_factor
    if day_fidelity > 1:
        # calculate rolling averages every `day_fidelity` days, then drop the inbetween days
        # this lowers the size of the dataframe which improves runtime of the HTML
        all_state_timelines = (
            (
                all_state_timelines.groupby(["state", "chain_particle"])
                .rolling(window=day_fidelity, on="date")
                .mean()
                .reset_index()
            )
            .drop(["level_2"], axis=1, inplace=False)
            .iloc[::day_fidelity, :]
        )
    return all_state_timelines


def _combine_state_timelines(cache_paths, states):
    all_state_timelines = pd.DataFrame()
    for cache_path, state in zip(cache_paths, states):
        timeline_path = os.path.join(
            cache_path, "azure_visualizer_timeline.csv"
        )
        if not os.path.exists(timeline_path):
            raise FileNotFoundError(
                "attempted to visualize an overview from %s without an `azure_visualizer_timeline.csv` file"
                % cache_path
            )
        timelines = pd.read_csv(timeline_path)
        assert (
            "date" in timelines.columns
        ), "something went wrong in the creation of azure_visualizer_timeline.csv, there is no date column"
        # count the `chain_particle` column, if it exists,
        # to figure out how many particles we are working with
        # if the column does not exist, na_na as placeholder
        if "chain_particle" not in timelines.columns:
            timelines["chain_particle"] = "na_na"
        timelines["state"] = state
        all_state_timelines = pd.concat(
            [all_state_timelines, timelines], axis=0, ignore_index=True
        )
    return all_state_timelines


def load_default_timelines(
    cache_paths: list[str],
    states: list[str],
    state_pop_sizes: list[float],
    day_fidelity: int,
    plot_types: np.ndarray[str],
    plot_titles: np.ndarray[str],
    plot_normalizations: np.ndarray[int],
    overview_subplot_width: int,
    overview_subplot_height: int,
) -> plotly.graph_objs.Figure:
    """
    Given a path to a folder containing downloaded azure files, checks for the existence
    of the azure_visualizer_timeline csv, if it exists, returns an overview figure
    of the timelines provided in the csv, raises a FileNotFoundError if csv
    is not found within `cache_path`

    Parameters
    ----------
    cache_paths: list[str]
        list of paths to the local files being visualized.
    states: list[str]
        parallel list to cache_paths marking the state contained within each cache_path
    plot_types: np.ndarray[str]
        numpy array of strings representing all the plot types able to be plotted
        if they are not found within azure_visualizer_timeline they are skipped
    plot_titles: np.ndarray[str]
        numpy array of strings parallel to `plot_types` representing the plot titles
        in a more human readable format
    overview_subplot_width: int
        integer representing pixel width of each subplot in the overview
    overview_subplot_height: int
        integer representing pixel height of each subplot in the overview

    Returns
    -------
    Figure
        plotly Figure with `n` rows and `m` columns where `n` is the number of plots
        within azure_visualizer_timeline identified by OVERVIEW_PLOT_TYPES global var.
    """
    num_states = len(states)
    all_state_timelines = _combine_state_timelines(cache_paths, states)

    num_individual_particles = len(
        all_state_timelines["chain_particle"].unique()
    )
    # we are counting the number of plot_types that are within timelines.columns
    # this way we dont try to plot something that timelines does not have
    plots_in_timelines = [
        any([plot_type in col for col in all_state_timelines.columns])
        for plot_type in plot_types
    ]
    num_unique_plots_in_timelines = sum(plots_in_timelines)
    # select only the plots we actually find within `timelines`
    plot_types = plot_types[plots_in_timelines].tolist()
    plot_titles = plot_titles[plots_in_timelines].tolist()
    plot_normalizations = plot_normalizations[plots_in_timelines].tolist()
    # normalize our dataframe by the given y axis normalization schemes
    all_state_timelines = _cleanup_and_normalize_timelines(
        all_state_timelines,
        day_fidelity,
        plot_types,
        plot_normalizations,
        states,
        state_pop_sizes,
    )
    # some more plotly hacking to space the titles correctly
    plot_titles_spaced = (
        np.array(
            [
                [plot_title] + [""] * (num_states - 1)
                for plot_title in plot_titles
            ]
        )
        .flatten()
        .tolist()
    )
    # total_subplots = num_plots_in_timeline * num_states
    fig = make_subplots(
        rows=num_unique_plots_in_timelines,
        cols=num_states,
        shared_xaxes=True,
        shared_yaxes=True,
        x_title="date",
        row_heights=[overview_subplot_height] * num_unique_plots_in_timelines,
        column_widths=[overview_subplot_width] * num_states,
        column_titles=states,
        subplot_titles=plot_titles_spaced,
        horizontal_spacing=0.01,
        vertical_spacing=0.03,
    )

    # go through each plot type, look for matching columns within `timlines` and plot
    # that plot_type for each chain_particle pair. plotly rows/cols are index at 1 not 0
    for state_num, state in enumerate(states, start=1):
        print("Plotting State : " + state)
        for plot_num, (plot_title, plot_type) in enumerate(
            zip(plot_titles, plot_types), start=1
        ):
            # for example "vaccination_" in "vaccination_0_17" is true
            # so we include this column in the plot under that plot_type
            columns_to_plot = [
                col for col in all_state_timelines.columns if plot_type in col
            ]
            # generates a big figure of the column(s) of interest, possibly grouped by chain_particle
            plot_by_chain_particle = _create_figure_from_timeline(
                all_state_timelines[all_state_timelines["state"] == state],
                plot_title,
                x_axis="date",
                y_axis=columns_to_plot,
                plot_type=plot_type,
                group_by="chain_particle",
            )

            fig.add_traces(
                plot_by_chain_particle["data"], rows=plot_num, cols=state_num
            )
            # ruff: noqa: E731
            selector = lambda data: "remove_duplicate" not in data["name"]

            if num_individual_particles > 1:
                fig.update_traces(opacity=0.5, row=plot_num, col=state_num)
                medians = (
                    all_state_timelines[all_state_timelines["state"] == state]
                    .groupby(by=["date"])[columns_to_plot]
                    .median()
                )
                medians = medians.reset_index()
                # no group by since we collapsed chain_particle dim
                median_lines = _create_figure_from_timeline(
                    medians,
                    plot_title,
                    x_axis="date",
                    y_axis=columns_to_plot,
                    plot_type=plot_type,
                )
                for data in median_lines["data"]:
                    data["opacity"] = 1.0
                    data["name"] = data["name"] + " Median"
                fig.add_traces(
                    median_lines["data"], rows=plot_num, cols=state_num
                )
                # if we are plotting medians, have those display in the legend
                # ruff: noqa: E731
                selector = lambda data: "Median" in data["name"]
        # only show 1 legend since all states have same schema
        fig.update_traces(
            showlegend=True,
            selector=selector,
            col=1,
        )
        # show tooltips for medians/single particle value to 4 sig figs
        fig.update_traces(hovertemplate="%{y:.4g}", selector=selector)
        _generate_row_wise_legends(fig, num_states)
        # lastly we update the whole figure's width and height with some padding
    print("displaying overview plot...")
    fig.update_layout(
        width=overview_subplot_width * num_states + 50,
        height=overview_subplot_height * num_unique_plots_in_timelines + 50,
        title_text="",
        hovermode="x unified",
    )

    # update each plots description to be far left
    fig.update_annotations(
        font_size=16,
        x=0.0,
        xanchor="left",
        selector=lambda data: data["text"] in plot_titles,
    )
    # update state column labels to be in center of each column
    fig.update_annotations(
        font_size=12,
        xanchor="center",
        selector=lambda data: data["text"] in states,
    )

    return fig


def shiny_to_plotly_theme(shiny_theme: str):
    """shiny themes are "dark" and "light", plotly themes are
    "plotly_dark" and "plotly_white", this function converts from shiny to plotly theme names

    Parameters
    ----------
    shiny_theme : str
        shiny theme as str

    Returns
    -------
    str
        plotly theme as str, used in `fig.update_layout(template=theme)`
    """
    return "plotly_%s" % (shiny_theme if shiny_theme == "dark" else "white")


def shiny_to_matplotlib_theme(shiny_theme: str):
    """shiny themes are "dark" and "light", matplotlib themes are
    "dark_background" and "plotly_white", this function converts from shiny to plotly theme names
    Parameters
    ----------
    shiny_theme : str
        shiny theme as str
    Returns
    -------
    str
        plotly theme as str, used in `fig.update_layout(template=theme)`
    """
    return (
        "dark_background"
        if shiny_theme == "dark"
        else "tableau-colorblind10"  # "_classic_test_patch"
    )
