import sys
import os
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle

# colors from http://mkweb.bcgsc.ca/colorblind/
COLORS = {"orange":"#e69f00",
          "sky_blue":"#56b4e9",
          "bluish_green":"#009e73",
          "yellow":"#f0e442",
          "blue":"#0072b2",
          "vermillion":"#d55e00",
          "reddish_purple":"#cc79a7",
          "black":"#000000"}

def parse_args(args):
    parser = argparse.ArgumentParser(
        description="A tool to draw Manhattan plot from sumstat files.")

    parser.add_argument("sumstats", nargs="+", help="A list of sumstat files")
    parser.add_argument("--sep", nargs="+", default=['\t'],
        help="A list of column separators in sumstat files")
    parser.add_argument("--snp", nargs="+", default=["SNP"],
        help="A list of columns with SNP ids in sumstat files")
    parser.add_argument("--chr", nargs="+", default=["CHR"],
        help="A list of columns with SNP chromosomes in sumstat files")
    parser.add_argument("--bp", nargs="+", default=["BP"],
        help="A list of columns with SNP positions in sumstat files")
    parser.add_argument("--p", nargs="+", default=["PVAL"],
        help="A list of columns with SNP p-values in sumstat files")

    parser.add_argument("--outlined", nargs="+", default=["NA"],
        help=("A list of files with ids of SNPs to mark with outlined bold dots, 'NA' if absent. "
            "These files should contain a single column with SNP ids without header"))
    parser.add_argument("--bold", nargs="+", default=["NA"],
        help=("A list of files with ids of SNPs to mark with bold dots, 'NA' if absent. "
            "These files should contain a single column with SNP ids without header"))
    parser.add_argument("--annot", nargs="+", default=["NA"],
        help=("A list of files with ids (1st column) and labels (2nd column) of SNPs to annotate, 'NA' if absent. "
            "These files should contain a two columns (1st: SNP ids, 2nd: SNP labels) without header"))
    # the next two options are shortcuts for --outlined and --bold to work
    # directly with the output of "sumstats.py clump". These options probably
    # should be removed in future for clarity
    parser.add_argument("--lead", nargs="+", default=["NA"],
        help=("A list of files with ids of lead SNPs, 'NA' if absent. "
            "These files should be the output of 'sumstats.py clump'"))
    parser.add_argument("--indep", nargs="+", default=["NA"],
        help=("A list of files with ids of independent significant SNPs, 'NA' if absent. "
        "These files should be the output of 'sumstats.py clump'"))

    parser.add_argument("--p-thresh", type=float, default=5.E-8,
        help="Significance threshold for p-values")
    parser.add_argument("--transparency", type=float, nargs="+", default=[1],
        help="Transparency level of points")
    parser.add_argument("--between-chr-gap", type=float, default=0.1,
        help="Size of the gap between chromosomes in the figure")
    parser.add_argument("--downsample-frac", nargs="+", type=float,
        default=[0.005], help="Fraction of SNPs to take for plotting")
    parser.add_argument("--chr2use", type=str, default="1-22",
        help=("Chromosome ids to plot (e.g. 1,2,3 or 1-4,12,16-20 or 19-22,X,Y). "
            "The order in the figure will correspond to the order in this argument. "
            "Chromosomes with non-integer ids should be indicated separately"))
    parser.add_argument("--striped-background", action="store_true",
        help="Draw grey background for every second chromosome")
    parser.add_argument("--seed", type=int, default=1, help="Random seed")
    parser.add_argument("--out", default="manhattan.png", help="Out file name")

    return parser.parse_args(args)


def process_args(args):
    """
    Check whether provided arguments are correct, change list-type arguments
    with single value to have a length = length of sumstats argument and process
    chr2use arument.
    """
    for f in args.sumstats:
        assert os.path.isfile(f), "'%s' file doesn't exist" % f
    for f in args.outlined:
        assert os.path.isfile(f) or f=="NA", "'%s' file doesn't exist" % f
    for f in args.bold:
        assert os.path.isfile(f) or f=="NA", "'%s' file doesn't exist" % f
    for f in args.lead:
        assert os.path.isfile(f) or f=="NA", "'%s' file doesn't exist" % f
    for f in args.indep:
        assert os.path.isfile(f) or f=="NA", "'%s' file doesn't exist" % f
    for f in args.annot:
        assert os.path.isfile(f) or f=="NA", "'%s' file doesn't exist" % f

    n = len(args.sumstats)
    arg_dict = vars(args)
    for arg_name, arg_val in arg_dict.items():
        if (type(arg_val) is list) and (len(arg_val)<n) and (len(arg_val)==1):
            arg_dict[arg_name] = arg_val*n
    chr2use_arg = arg_dict["chr2use"]
    chr2use = []
    for a in chr2use_arg.split(","):
        if "-" in a:
            start, end = [int(x) for x in a.split("-")]
            chr2use += [str(x) for x in range(start, end+1)]
        else:
            chr2use.append(a.strip())
    arg_dict["chr2use"] = chr2use

    msg = " option should have a value for each sumstat file or a single value"
    assert len(args.sep) == n, "--sep" + msg
    assert len(args.snp) == n, "--snp" + msg
    assert len(args.chr) == n, "--chr" + msg
    assert len(args.bp) == n, "--bp" + msg
    assert len(args.p) == n, "--p " + msg
    assert len(args.downsample_frac) == n, "--downsample-frac" + msg

def get_snp_ids(fname):
    if fname == "NA":
        return np.array([])
    else:
        return pd.read_table(fname,header=None,squeeze=True).values

def get_lead(fname):
    if fname == "NA":
        return np.array([])
    else:
        df = pd.read_table(fname)
        return df.loc[df.is_locus_lead,"LEAD_SNP"].values

def get_indep_sig(fname):
    if fname == "NA":
        return np.array([])
    else:
        df = pd.read_table(fname)
        return df["INDEP_SNP"].values

def get_annot(fname):
    """
    Read annotation file and return 2 arrays: SNP ids and SNP labels in the
    corresponding order. Return two empty arrays if fname == "NA"
    """
    if fname == "NA":
        return np.array([]), np.array([])
    else:
        df = pd.read_table(fname,header=None,names=["snp", "label"])
        return df.snp.values, df.label.values


def filter_sumstats(sumstats_f, sep, snpid_col, pval_col, chr_col, bp_col, chr2use):
    """
    Filter original summary stats file.
    Args:
        sumstats_f: sumstats file name
        sep: column separator in sumstats_f
        snpid_col: a name of column with variant ids
        pval_col: a name of column with variant p-values
        chr_col: a name of column with variant chromosomes
        bp_col: a name of column with variant positions on chromosome
        chr2use: chromosomes to use for plotting (other are dropped)
    Returns:
        df: filtered DataFrame
    """
    print("Filtering %s" % sumstats_f)
    cols2use = [snpid_col, pval_col, chr_col, bp_col]
    df = pd.read_table(sumstats_f, usecols=cols2use, index_col=snpid_col, sep=sep,
        dtype={chr_col:str})
    print("%d SNPs in %s" % (len(df), sumstats_f))
    df.dropna(subset=[pval_col], how="all", inplace = True)
    print("%d SNPs with defined p-value" % len(df))
    df = df.loc[df[chr_col].isin(chr2use),:]
    print("%d SNPs within specified chromosomes" % len(df))
    # TODO: zero filtering step is very slow, should be optimized
    df = df.loc[df[pval_col]>0,:]
    print("%d SNPs with non-zero p-value" % len(df))
    return df


def get_df2plot(df, outlined_snps_f, bold_snps_f, lead_snps_f, indep_snps_f,
    annot_f, downsample_frac, pval_col):
    """
    Select variants which will be plotted. Mark lead and independent significant
    variants if corresponding information is provided.
    Args:
        df: DataFrame for variant selection
        outlined_snps_f: a name of file with SNP ids to plot with outlined bold dots
        bold_snps_f: a name of file with SNP ids to plot with bold dots
        lead_snps_f: a name of file with lead variants
        indep_snps_f: a name of file with independent significant variants
        downsample_frac: a fraction of variants which will be sampled from df
            for plotting
        pval_col: a column with p-values in df
    Returns:
        df2plot: DataFrame with variants for plotting
    """
    print("Preparing SNPs for plotting")
    # define a subset of variants which will be plotted:
    # [outlined + lead] + [bold + indep] + sample
    outlined_snp_ids = get_snp_ids(outlined_snps_f)
    bold_snp_ids = get_snp_ids(bold_snps_f)
    lead_snp_id = get_lead(lead_snps_f)
    indep_snp_id = get_indep_sig(indep_snps_f)
    annot_snp_ids, annot_snp_labels = get_annot(annot_f)
    outlined_snp_ids = np.unique(np.concatenate((outlined_snp_ids, lead_snp_id)))
    bold_snp_ids = np.unique(np.concatenate((bold_snp_ids, indep_snp_id)))
    # sample variants 
    n = int(downsample_frac*len(df))
    # w = 1/df[pval_col].values
    w = -np.log10(df[pval_col].values)
    w /= sum(w)
    snp_sample = np.random.choice(df.index,size=n,replace=False,p=w)
    # TODO: keep SNPs within identified loci with higher prob?
    # NOTE: it could be that there are snp ids in outlined_snp_ids or bold_snp_ids which
    # are not in df.index, therefore we should take an index.intersection first.
    outlined_snp_ids = df.index.intersection(outlined_snp_ids)
    bold_snp_ids = df.index.intersection(bold_snp_ids)
    annot_snp_ids = df.index.intersection(annot_snp_ids)
    snps2keep = np.unique(np.concatenate((outlined_snp_ids, bold_snp_ids,
        snp_sample, annot_snp_ids)))
    df2plot = df.loc[snps2keep,:]
    df2plot.loc[:,"outlined"] = False
    df2plot.loc[outlined_snp_ids,"outlined"] = True
    df2plot.loc[:,"bold"] = False
    df2plot.loc[bold_snp_ids,"bold"] = True
    df2plot.loc[:,"annot"] = ""
    df2plot.loc[annot_snp_ids,"annot"] = annot_snp_labels
    print("%d outlined SNPs" % len(outlined_snp_ids))
    print("%d bold SNPs" % len(bold_snp_ids))
    print("%d annotated SNPs" % len(annot_snp_ids))
    print("%d SNPs will be plotted in total" % len(df2plot))
    return df2plot


def get_chr_df(dfs2plot, bp_cols, chr_cols, between_chr_gap, chr2use):
    """
    Construct DataFrame with index = chromosome names and 5 columns:
    min: minimum coordinate on each chromosome among all dfs in dfs2plot
    max: maximum coordinate on each chromosome among all dfs in dfs2plot
    ind: index of the chromosome = 1:N, where N - nuumber of different chromosomes
    rel_size: size of the chromosome relative to the first chromosome (i.e.
        rel_size of the first chr = 1)
    start: start coordinate of the chromosome on the x axis, where the first
        chromosome starts at x = 0 and ends at x = 1 (if its size = 1), taking
        into account between_chr_gap
    Args:
        dfs2plot: a list of DataFrames that will be plotted
        bp_cols: name of marker position on chromosome columns
        chr_cols: name of marker chromosome columns
        between_chr_gap: gap between end of chr K and start of chr K+1
        chr2use: chromosomes to use for plotting (other are dropped)
    Returns:
        chr_df: a DataFrame with chromosome information as described above
    """
    unique_chr = np.unique(np.concatenate([df[chr_cols[i]].unique() for i,df in enumerate(dfs2plot)]))
    unique_chr = [c for c in chr2use if c in unique_chr]
    chr_df = pd.DataFrame(index=unique_chr, columns=["min","max","ind","start","rel_size"])
    min_df = pd.DataFrame(index=unique_chr)
    max_df = pd.DataFrame(index=unique_chr)
    for i,df in enumerate(dfs2plot):
        chr_min = df.groupby(chr_cols[i])[bp_cols[i]].min()
        chr_max = df.groupby(chr_cols[i])[bp_cols[i]].max()
        min_df[i] = chr_min
        max_df[i] = chr_max
    chr_df["min"] = min_df.min(axis=1)
    chr_df["max"] = max_df.max(axis=1)
    chr_df["ind"] = np.arange(len(unique_chr))
    # use the first chr form unique_chr as a reference unit size
    ref_unit_size = chr_df.loc[chr_df.index[0],"max"] - chr_df.loc[chr_df.index[0],"min"]
    chr_df["rel_size"] = (chr_df["max"] - chr_df["min"])/ref_unit_size
    chr_df["start"] = chr_df["rel_size"].cumsum() - chr_df["rel_size"] + between_chr_gap*chr_df["ind"]
    return chr_df


def add_coords(df2plot, chr_col, bp_col, pval_col, chr_df):
    """
    Modify provided DataFrame df2plot by adding columns with x-y coordinates for
    plotting to it.
    Args:
        df2plot: DataFrame with variants for plotting (produced by get_df2plot)
        chr_col: a column with chromosome of variants in df2plot
        bp_col: a column with position on chromosome of variants in df2plot
        pval_col: a column with variant p-values
        chr_df: a DataFrame with chromosome information (produced by get_chr_df)
    """
    chr_start = chr_df.loc[df2plot[chr_col], "start"].values
    chr_min = chr_df.loc[df2plot[chr_col], "min"].values
    df2plot.loc[:,"x_coord"] = (df2plot[bp_col] - chr_min)/chr_df.loc[chr_df.index[0],"max"] + chr_start
    df2plot.loc[:,"log10p"] = -np.log10(df2plot[pval_col]) # y coord


def add_striped_background(chr_df, ax, y_up):
    """
    Add grey background rectagle for every second chromosome.
    """
    height = y_up
    background_rect = []
    for c in chr_df.index[1::2]:
        x = chr_df.loc[c,"start"]
        y = 0
        width = chr_df.loc[c,"rel_size"]
        rect = Rectangle((x, y), width, height)
        background_rect.append(rect)
    pc = PatchCollection(background_rect, facecolor='#AEA79F', alpha=0.3,
                         edgecolor='None')
    ax.add_collection(pc)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    process_args(args)

    np.random.seed(args.seed)

    sumstat_dfs = [
        filter_sumstats(s, args.sep[i], args.snp[i], args.p[i], args.chr[i], args.bp[i], args.chr2use)
        for i,s in enumerate(args.sumstats)]

    dfs2plot = [get_df2plot(df, args.outlined[i], args.bold[i], args.lead[i],
                            args.indep[i], args.annot[i], args.downsample_frac[i], args.p[i])
        for i, df in enumerate(sumstat_dfs)]

    chr_df = get_chr_df(dfs2plot, args.bp, args.chr, args.between_chr_gap, args.chr2use)

    for i,df in enumerate(dfs2plot):
        add_coords(df, args.chr[i], args.bp[i], args.p[i], chr_df)

    # make plot
    print("Making plot")
    fig, ax = plt.subplots(figsize=(14,5), dpi=200)

    # find upper limit for Y axis
    y_up = max([df["log10p"].max() for df in dfs2plot])
    y_up = max(y_up, -np.log10(args.p_thresh))
    y_up *= 1.05

    if args.striped_background:
        add_striped_background(chr_df, ax, y_up)

    for i, df in enumerate(dfs2plot):
        # plot normal points
        color = "C%d" % i
        ax.plot(df["x_coord"], df["log10p"], ls=' ', marker='.', ms=1,
            color=color, alpha=args.transparency[i])
    for i, df in enumerate(dfs2plot):
        # plot bold significant and outlined variants "on top" of normal points
        color = "C%d" % i
        df_tmp = df.loc[df["bold"],:]
        ax.plot(df_tmp["x_coord"], df_tmp["log10p"], ls=' ', marker='o', ms=4,
            color=color)
        df_tmp = df.loc[df["outlined"],:]
        ax.plot(df_tmp["x_coord"], df_tmp["log10p"], ls=' ', marker='o', ms=5,
            markeredgewidth=0.6, markeredgecolor='k', color=color)
        df_tmp = df.loc[df["annot"]!="",["annot","x_coord", "log10p"]]
        for row in df_tmp.itertuples():
            ax.annotate(row.annot, xy=(row.x_coord, row.log10p), xycoords='data',
                xytext=(2,2), textcoords='offset points', color=color, style='italic') # fontsize=20


    ax.hlines([-np.log10(args.p_thresh)], 0, 1, colors='k', linestyles='dotted',
        transform=ax.get_yaxis_transform())

    # TODO: annotate outlined (or any specified SNPs) SNPs

    x_ticks = chr_df["start"] + 0.5*chr_df["rel_size"]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(map(str, x_ticks.index))

    ax.set_xlim((-0.1, chr_df.loc[chr_df.index[-1], "start"] + chr_df.loc[chr_df.index[-1], "rel_size"] + 0.1))
    y_low = ax.get_ylim()[0]
    ax.set_ylim((0-0.005*y_up, y_up))
    # remove top and right spines
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    # add offset for left spine
    ax.spines['left'].set_position(('outward',5))
    ax.spines['bottom'].set_position(('outward',5))

    ax.set_xlabel("Chromosome")
    ax.set_ylabel(r"$\mathrm{-log_{10}(conjFDR)}$")

    plt.tight_layout()

    # save/show
    # plt.savefig(args.out)
    plt.savefig(args.out)
    # plt.show()
    print("%s was generated" % args.out)