import matplotlib
import matplotlib.pyplot as plt
import os
import shutil
import functools
import sys
from multiprocessing import Pool


CACHE_DIR = ".figcache"


def _parallel_plot_worker(args, plot_fn, figsize, preprocessing_fn=None):
    index, data = args

    if preprocessing_fn is not None:
        data = preprocessing_fn(data)

    fig = plt.figure(figsize=figsize)
    matplotlib.font_manager._get_font.cache_clear()  # necessary to reduce text corruption artifacts
    axes = plt.axes()

    plot_fn(data, fig, axes)

    path = f"{CACHE_DIR}/{index}.temp.png"
    plt.savefig(path, bbox_inches="tight", pad_inches=0)

    return index, path


def parallel_plot(plot_fn, data, grid_shape, total=None, preprocessing_fn=None, col_labels=None, row_labels=None,
                  grid_cell_size=(6, 12), switch_axis=False, cleanup=True, show_progress=True):
    """
    Generate a grid of plots, where each plot inside the grid is generated by another process,
    effectively allowing parallel plot generation.

    :param plot_fn: Plot function that will be called from the process context. Lambda expressions are not supported.
    :param data: Iteratable data with length of rows * cols.
    :param grid_shape: Shape of the grid as (rows, cols) tuple. For a horizontal list provide (N, 1) and for a vertical
    list provide (1, N).
    :param total: Length of the data. Must be provided if the passed data length cannot be accessed by calling len()
    e.g. on generators
    :param preprocessing_fn: Optional preprocessing function that is called from the process context on the data chunk
    before plotting. Lambda expressions are not supported.
    :param col_labels: Optional list of column labels.
    :param row_labels: Optional list of row labels.
    :param grid_cell_size: Size of each cell (subplot) as (width, height) tuple. This has a direct impact on the parent
    plot size.
    :param switch_axis: If false the grid will be populated from left to right, top to bottom. Otherwise, it will be
    populated top to bottom, left to right.
    :param cleanup: If true, the generated cache directory will be deleted before finishing. Can be useful for
    debugging.
    :param show_progress: If true, shows a progressbar of the plotting. Requires the tqdm module.

    :return: fig, axes of the parent plot.
    """

    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)

    n_rows = grid_shape[0]
    n_cols = grid_shape[1]

    if total is None:
        total = len(data)

    full_figsize = (n_cols * grid_cell_size[0], n_rows * grid_cell_size[1])

    fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=full_figsize, squeeze=False)

    if col_labels is not None:
        for label, ax in zip(col_labels, axes[0]):
            ax.set_title(label, loc='center', wrap=True)

    if row_labels is not None:
        for label, ax in zip(row_labels, axes[:, 0]):
            ax.set_ylabel(label, loc='center', wrap=True)

    for ax in axes.flatten():
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    worker_func = functools.partial(_parallel_plot_worker, plot_fn=plot_fn, figsize=grid_cell_size,
                                    preprocessing_fn=preprocessing_fn)

    with Pool(min(total, os.cpu_count())) as pool:

        iterator = pool.imap_unordered(worker_func, zip(range(total), data))
        if show_progress:
            from tqdm import tqdm
            iterator = tqdm(iterator, total=total)

        for index, path in iterator:
            img = plt.imread(path)

            if switch_axis:
                c = int(index / n_rows)
                r = index % n_rows
            else:
                c = index % n_cols
                r = int(index / n_cols)

            axes[r, c].imshow(img)

    if cleanup:
        shutil.rmtree(CACHE_DIR)

    return fig, axes
