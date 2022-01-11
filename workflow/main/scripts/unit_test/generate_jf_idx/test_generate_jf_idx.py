#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##############################################################################

# Tigerfish
# generate_jf_idx.py

"""
Created on Wed Jun 23 16:56:01 2021
@author: Robin Aguilar
Beliveau and Noble Labs
University of Washington | Department of Genome Sciences
"""
##############################################################################

#specific script name
scriptName = "generate_jf_idxs"

#import libraries
import time
import argparse
from itertools import islice
from operator import itemgetter, attrgetter
import subprocess
import numpy as np
import pandas as pd
from itertools import groupby
import re

#import biopython libraries
from Bio.Seq import Seq
from Bio import SeqIO

##############################################################################

def test_find_scaffolds(fa_file,chrom,scaffold_fa):
    """
    Generates fasta file of desired chromosome
    
    Parameters
    ----------
    fa_file : fasta file
        Multi lined Genome fasta file.
    chrom : string
        chromosome string to subset
    Returns
    -------
    scaffold_fa : fasta file
        fasta file of chromosome that was subset

    Assertions being tested
    -----------------------
    - That chromosome in param identifies appropriate chromosome
    - If chrom does not match, or other keyword entered, exit program
    - Output fasta is written
    """

    #make tiny fasta that will do assertion and test
    fasta_sequences = SeqIO.parse(open(fa_file),'fasta')

    for fasta in fasta_sequences:
        if fasta.id != chrom:
            print("Please enter valid scaffold. Exiting.")
            exit()
        else:
            assert(fasta.id == chrom)

            #writes selected chromosome to output
            SeqIO.write(fasta,scaffold_fa,"fasta")

    return scaffold_fa

##############################################################################

def test_jf_query(jf_idx,scaffold_fa,jf_out,k_mer_length):
    
    """
    Runs jellyfish to generate a query file from the jellyfish index provided
    Parameters
    ----------
    jf_idx : jellyfish index file
        genome wide jellyfish index file
    scaffold_fa : fasta file
        chromosome fasta file generated by find_scaffold()
    Returns
    -------
    jf_out : jellyfish count file
        file that describes k-mer counts in genome

    Assertions being tested
    -----------------------
    - Jellyfish is called.
    - Jellyfish index is made to correct specification.
    """
    
    #call subprocess to generate query count of k-mers for given fasta
    #validates newly generated fasta file
    subprocess.call(['jellyfish', 'query', jf_idx, '-s',
                     scaffold_fa, '-o', jf_out], stderr=None, shell=False)
    
    #sees if file exists and can be read properly
    jf_file_check = open(jf_out,'r')
    jf_lines = jf_file_check.readlines()

    #reads each line in file
    k_mer_list = [line.split()[0] for line in jf_lines]

    #validates valid jellyfish file of specified k-mer length
    assert(len(k_mer_list[0]) == int(k_mer_length))

    return jf_out

##############################################################################

def test_map_coords(scaffold_fa):
    
    """
    This function will take a the chrom fasta file it and identify where 
    all N and non-N bases are located
    Parameters
    ----------
    scaffold_fa : fasta file
        chromosome fasta file generated by find_scaffold()
    Returns
    -------
    bases_dist_start : list
        list to populate with location of ATCG bases (ints)
    n_bases_start : list
        list to populate with location of ATCG bases (ints)

    Assertions being tested
    -----------------------
    - Lists of base positions are generated correctly with ATCGN bases.
    - Bases match
    """
    
    #lists to populate locations of base types, ATCG or N
    bases_dist_start=[]
    n_bases_start=[]
   
    #open fasta file
    fa_seq = list(SeqIO.parse(open(scaffold_fa),'fasta'))
    
    for fasta in fa_seq:
        sequence=str(fasta.seq).lower()
        #first identified where ATCG bases are located
        
        for match in re.finditer('[atcg]',sequence):
            bases_dist_start.append(int(match.start()))
            
        #identifies the location of N bases
        for match in re.finditer('[n]', sequence):
            n_bases_start.append(int(match.start()))

        #take the length of the bases and the n bases if any
        standard_base_list_len = len(bases_dist_start)
        n_bases_start_len = len(n_bases_start)

        #validate that the sequence length matches the length of bases
        assert(len(sequence) == standard_base_list_len + n_bases_start_len)
 
    return bases_dist_start,n_bases_start

##############################################################################

def test_group_ranges(scaffold_fa):
    
    """
    This function will return lists continous ranges of N and non-N bases.
    Parameters
    ----------
    bases_dist_start : list
        list containing location of ATCG bases as ints
    n_bases_start : list
        list containing locatio of N bases (if any) as ints
    Returns
    -------
    tuples of continuous ATCG bases (ranges)
    tuples of continuous N bases (n_ranges)

    Assertions being tested
    -----------------------
    - Returns tuples of independent ranges of ATCG and/or N bases
    """

    bases_dist_start,n_bases_start = test_map_coords(scaffold_fa)

    ranges = []
    n_ranges=[]
    
    #this collapses the set of the ATCG bases to provide  ranges in a list
    for k, g in groupby(enumerate(bases_dist_start), lambda x: x[1]-x[0]):
        group = list(map(itemgetter(1), g))
        ranges.append(str(group[0]) + "\t" + str(group[-1]+1))

    #if there happen to be unmapped bases "N" masked in the queried genome
    if n_bases_start:
        #this collapses the set of N bases to provide ranges in a list 
        for k, g in groupby(enumerate(n_bases_start), lambda x: x[1]-x[0]):
            group=list(map(itemgetter(1),g))
            n_ranges.append(str(group[0]) + "\t" + str(group[-1]+1))

    #checks if n_ranges if provided are made appropriately
    #reads in fasta as a string
    fa_seq = list(SeqIO.parse(open(scaffold_fa),'fasta'))

    #read fasta sequence as string
    for fasta in fa_seq:
        sequence=str(fasta.seq).lower()
    
    #use regex to find the instances of "nnnnnnnnnn", there are 2 in test
    regex = "nnnnnnnnnn"
    match = re.findall(regex,sequence)

    #returns that two ranges are mapped of N bases
    assert(len(match) == len(n_ranges))

    return ranges,n_ranges

##############################################################################

def test_create_df_ranges(scaffold_fa):
    """
    This function is used to call on the compute ranges function and handle
    ranges if N bases are present in the fasta file
    
    Parameters
    ----------
    ranges : tuples
        tuples of continous ranges for ATCG basesw
    n_ranges : tuples
        tuples of continuous ranges for N bases
    n_bases_start : list
        list of start values if N bases are present in genome
    Returns
    -------
    probes_ranges : dataframe
        contacenated ranges that includes N if present in genome, else this
        returns a dataframe with continous coordinates of ATCG bases

    Assertions being tested
    -----------------------
    - Returns dataframe ranges for ATCG and N seperately
    - Returns merged dataframe including correct positions of ATCGN
    """

    ranges,n_ranges = test_group_ranges(scaffold_fa)

    #compute a dataframe for normal regions that are not N
    
    probes_ranges=compute_ranges(ranges,"R")

    #do the ATCG ranges match the expected length
    assert(len(ranges) == len(probes_ranges))
    
    #compute the dataframe for each respective range if N's are found
    
    if n_ranges:
        n_ranges_df=compute_ranges(n_ranges,"N")

        #checks length of N base regions
        assert(len(n_ranges_df) == len(n_ranges))
        
        probes_ranges=merge_ranges(probes_ranges,n_ranges_df)

    #checks if the total lengths of all flagged regions match
    assert(len(probes_ranges) == len(ranges) + len(n_ranges_df))

    #return that dataframe
    return probes_ranges
    
##############################################################################

def compute_ranges(base_ranges,label):
    
    """
    Helper function called in create_df_ranges()
    
    Parameters
    ----------
    base_ranges : tuples
        this list contains either the ATCG base list or N base list
    label : string
        "R" represents ATCG bases and "N" represents N bases
    Returns
    -------
    num_ranges : dataframe
        dataframe containing start and end of labeled regions, tab seperated

    """
    
    #make a dataframe of bases
    ranges_v=pd.DataFrame(list(base_ranges), columns=['ranges'])
    
    #split the start and end to be seperate columns
    ranges_v[['start','end']] = ranges_v.ranges.str.split(expand=True)

    #casts columns as int of start and end of region
    num_start=ranges_v['start'].astype(int)
    num_end=ranges_v['end'].astype(int)
    num_ranges = pd.concat([num_start, num_end], axis=1)
 
    #label whether the range is of a normal base "R" or an N, "N"
    num_ranges['type']=str(label)

    return num_ranges

##############################################################################

def merge_ranges(norm_ranges,n_ranges):
    """
    Helper function called in create_df_ranges()
    
    Parameters
    ----------
    norm_ranges : dataframe
        dataframe of ranges for ATCG bases, cols are start, stop, range type
    n_ranges : dataframe
        dataframe of ranges for N bases, cols are start, stop, range type
    Returns
    -------
    reorder_df : dataframe
        merged dataframe that contains concatenated both N and R ranges
        if applicable.
    """
    
    #merges the two types of ranges if applicable
    merged_ranges = pd.concat([norm_ranges, n_ranges])
    merged_ranges.index = range(len(merged_ranges.index))
    
    #sorts the dataframes in ascending order
    sorted_df = merged_ranges.sort_values(by=['start'], ascending=True)
    reorder_df=sorted_df.set_index(np.arange(len(sorted_df.index)))
        
    return reorder_df

##############################################################################

def test_subtract_kmer_length(scaffold_fa,k_mer_length):
    """
    This function will take each row before each N type and deducts from it's
    end value the length of the kmer, all R regions are then put in a new DF
    
    Parameters
    ----------
    probes_ranges : dataframe
        takes the ordered base ranges in a dataframe
    Returns
    -------
    normal_ranges : dataframe containing only index location values of 
    ATCG bases

    Assertions being tested
    -----------------------
    - None. Dataframe logic is validated in final function
    """
    
    probes_ranges = test_create_df_ranges(scaffold_fa)

    #for each row contianing an N
    for index, row in probes_ranges.iloc[1:].iterrows():
        if row['type']=="N":
            prev=probes_ranges.index.get_loc(index-1)

            parse_rows=(probes_ranges.iloc[prev])
            
            #take into account the different, the start of the next k-mer
            probes_ranges.loc[prev,['end']]=parse_rows["end"] - int(k_mer_length)

    #subset all the R's into a seperate dataframe
    #for jellyfish file, serves as start of k-mer locations
    normal_ranges=probes_ranges.loc[(probes_ranges.type == "R")]

    return normal_ranges

##############################################################################

def test_generate_index_file(scaffold_fa,k_mer_length,index_out):
    """
    This function will take the two columns from the normal ranges DF and
    then append these ranges to a list. This list is then written out
    as a file.
    
    Parameters
    ----------
    normal_ranges : dataframe containing the adjusted integer locations of 
    ATCG bases with respect to k-mer value.
    Returns
    -------
    None. Writes file for continuous ATCG base location in the genome.

    Assertions being tested
    -----------------------
    - The length of test sequence should match final index location. 

    """

    normal_ranges = test_subtract_kmer_length(scaffold_fa,k_mer_length)
    #list to store the ranges in the dataframe
    kmer_indices=[]

    #make the dataframes into lists
    start_ranges_list = normal_ranges['start'].tolist()
    end_ranges_list = normal_ranges['end'].tolist()

    #then zip the two lists together
    for start,end in zip(start_ranges_list,end_ranges_list):
        for x in range (start, end+1):
            kmer_indices.append(x)

    #take length of fasta file into string
    #total length should match final position of created index
    #assertion shows all genomic positions are accounted for
    fa_seq = list(SeqIO.parse(open(scaffold_fa),'fasta'))

    for fasta in fa_seq:
        sequence=str(fasta.seq).lower()

    assert(len(sequence) == int(kmer_indices[-1]))
 
    #write the indices to file
    with open(index_out,"w") as k_file:
        for i in kmer_indices:
            k_file.write(str(i) + "\n")

##############################################################################
