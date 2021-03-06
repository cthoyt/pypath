#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
#  This file is part of the `pypath` python module
#
#  Copyright
#  2014-2019
#  EMBL, EMBL-EBI, Uniklinik RWTH Aachen, Heidelberg University
#
#  File author(s): Dénes Türei (turei.denes@gmail.com)
#                  Nicolàs Palacio
#
#  Distributed under the GPLv3 License.
#  See accompanying file LICENSE.txt or copy at
#      http://www.gnu.org/licenses/gpl-3.0.html
#
#  Website: http://pypath.omnipathdb.org/
#

from future.utils import iteritems
from past.builtins import xrange, range

import sys
import imp
import re
from collections import Counter, OrderedDict
import numpy as np

import pypath.dataio as dataio
import pypath.progress as progress
from pypath.common import *


# this is for GO terms parsing:
_rego = re.compile(r'and|or|not|\(|\)|GO:[0-9]{7}')


class GeneOntology(object):
    
    all_relations = {
        'is_a', 'part_of', 'occurs_in', 'regulates',
        'positively_regulates', 'negatively_regulates',
    }
    
    
    def __init__(self):
        """
        Loads data about Gene Ontology terms and their relations.
        """
        
        self._load()
    
    
    def reload(self):
        """Reloads the object from the module level."""
        
        modname = self.__class__.__module__
        mod = __import__(modname, fromlist=[modname.split('.')[0]])
        imp.reload(mod)
        new = getattr(mod, self.__class__.__name__)
        setattr(self, '__class__', new)
    
    
    def _load(self):
        
        self._load_terms()
        self._load_tree()
        self._set_aspect()
        self._set_name()
        self._set_term()
        
        delattr(self, '_terms')
    
    
    def _load_terms(self):
        
        self._terms = dataio.go_terms_quickgo()
    
    
    def _load_tree(self):
        
        self.ancestors = self._merge_aspects(
            dataio.go_ancestors_quickgo()
        )
        self.descendants = self._merge_aspects(
            dataio.go_descendants_quickgo()
        )
    
    
    def _set_aspect(self):
        
        self.aspect = dict(
            (term, asp)
            for asp, terms in iteritems(self._terms)
            for term in terms.keys()
        )
    
    
    def _set_name(self):
        
        self.name = dict(
            i
            for ii in self._terms.values()
            for i in iteritems(ii)
        )
    
    
    def _set_term(self):
        
        self.term = dict(
            reversed(i)
            for i in iteritems(self.name)
        )
    
    
    def get_name(self, term):
        """
        For a GO accession number returns the name of the term.
        """
        
        return None if term not in self.name else self.name[term]
    
    
    def get_term(self, name):
        """
        For a GO term name returns its GO accession number.
        """
        
        return None if name not in self.term else self.term[name]
    
    
    def terms_to_names(self, terms):
        """
        For a list of GO names returns a list of tuples with the terms
        and their names.
        """
        
        return [(term, self.get_name(name)) for term in terms]
    
    
    def terms_to_names_aspects(self, terms):
        """
        For a list of GO terms returns a list of tuples with the terms,
        their names and the ontology aspect.
        """
        
        return [
            (term, self.get_name(name), self.get_aspect(term))
            for term in terms
        ]
    
    
    def names_to_terms(self, names):
        """
        For a list of GO terms returns a list of tuples with the terms
        and their names.
        """
        
        return [(self.get_term(name), name) for name in names]
    
    
    def names_to_terms_aspects(self, names):
        """
        For a list of GO namess returns a list of tuples with the terms,
        their names and ontology aspects.
        """
        
        return [
            (self.get_term(name), name, self.aspect_from_name(name))
            for name in names
        ]
    
    
    def aspect_from_name(self, name):
        """
        Tells about a Gene Ontology term name which aspect does it belong to.
        """
        
        term = self.get_term(name)
        
        if term:
            
            return self.get_aspect(term)
    
    
    @staticmethod
    def _merge_aspects(dct):
        
        dct['P'].update(dct['C'])
        dct['P'].update(dct['F'])
        return dct['P']
    
    
    def subgraph_nodes(self, direction, terms, relations = None):
        """
        Returns a set of all nodes either in the subgraph of ancestors 
        or descendants of a single term or a set of terms.
        
        :param str direction:
            Possible values: `ancestors` or `descendants`.
        """
        
        relations = relations or self.all_relations
        
        if isinstance(terms, basestring):
            
            terms = {terms}
        
        graph = getattr(self, direction)
        subgraph = set()
        
        for term in terms:
            
            for related, relation in graph[term]:
                
                if relation not in relations:
                    
                    continue
                
                if related not in subgraph:
                    
                    subgraph.update(
                        self.subgraph_nodes(direction, related, relations)
                    )
                    subgraph.add(related)
        
        return subgraph
    
    
    def get_all_ancestors(self, terms, relations = None):
        """
        Returns a set of all ancestors of a single term or a set of terms.
        """
        
        return self.subgraph_nodes('ancestors', terms, relations)
    
    
    def get_all_descendants(self, terms, relations = None):
        """
        Returns a set of all descendants of a single term or a set of terms.
        """
        
        return self.subgraph_nodes('descendants', terms, relations)
    
    
    def get_aspect(self, term):
        """
        For a GO term tells which aspect does it belong to.
        Returns `None` if the term is not in the ontology.
        """
        
        if term in self.aspect:
            
            return self.aspect[term]
    
    
    def all_from_aspect(self, aspect):
        """
        Returns the set of all GO terms of one aspect.
        """
        
        return set(
            term
            for term, asp in iteritems(self.aspect)
            if asp == aspect
        )
    
    
    def is_root(self, term):
        """
        Tells if a term is the root of the graph i.e. it has no ancestors.
        """
        
        return term in self.ancestors and bool(self.ancestors[term])
    
    
    def is_leaf(self, term):
        """
        Tells if a term is a leaf of the graph i.e. it has no descendants.
        """
        
        return (
            (
                term in self.ancestors and
                term not in self.descendants
            ) or
            bool(self.descendants[term])
        )


class GOAnnotation(object):
    
    aspects = ('C', 'F', 'P')
    
    
    def __init__(self, organism = 9606, ontology = None):
        """
        For one organism loads Gene Ontology annotations, in addition it
        accepts or creates a ``GeneOntology`` object.
        """
        
        self.ontology = ontology or GeneOntology()
        
        annot = dataio.go_annotations_goa(organism = organism)
        self.c = annot['C']
        self.f = annot['F']
        self.p = annot['P']
        
        self._ancestors_annotate()
        self._merge_annotations()
    
    
    def reload(self):
        """
        Reloads the object from the module level.
        """
        
        modname = self.__class__.__module__
        mod = __import__(modname, fromlist = [modname.split('.')[0]])
        imp.reload(mod)
        new = getattr(mod, self.__class__.__name__)
        setattr(self, '__class__', new)
    
    
    def _ancestors_annotate(self):
        
        for asp in self.aspects:
            
            setattr(
                self,
                '%s_full' % asp.lower(),
                dict(
                    (
                        uniprot,
                        self.ontology.get_all_ancestors(annot)
                    )
                    for uniprot, annot in
                    iteritems(getattr(self, asp.lower()))
                )
            )
    
    
    def _merge_annotations(self):
        
        uniprots = self.all_uniprots()
        
        self.all = dict(
            (
                uniprot,
                set.union(*(
                    self.get_annot(uniprot, asp)
                    for asp in self.aspects
                ))
            )
            for uniprot in uniprots
        )
        
        self.all_full = dict(
            (
                uniprot,
                set.union(*(
                    self.get_annots(uniprot)
                    for asp in self.aspects
                ))
            )
            for uniprot in uniprots
        )
    
    
    def get_name(self, term):
        """
        For a GO accession number returns the name of the term.
        """
        
        return self.ontology.get_name(term)
    
    
    def get_term(self, name):
        """
        For a GO term name returns its GO accession number.
        """
        
        return self.ontology.get_term(name)
    
    
    def get_annot(self, uniprot, aspect):
        """
        For a UniProt ID returns its direct annotations from one aspect
        of Gene Ontology.
        Returns set.
        """
        
        annot = getattr(self, aspect.lower())
        return annot[uniprot] if uniprot in annot else set()
    
    
    def get_annots(self, uniprot):
        """
        For a UniProt ID returns its direct annotations from all aspects
        of Gene Ontology.
        Returns set.
        """
        
        return self.all[uniprot] if uniprot in self.all else set()
    
    
    def get_annot_ancestors(self, uniprot, aspect):
        """
        For a UniProt ID returns its annotations including lowest level
        terms and their ancestors from one aspect of Gene Ontology.
        Returns set.
        """
        
        annot = getattr(self, '%s_full' % aspect.lower())
        return annot[uniprot] if uniprot in annot else set()
    
    
    def get_annots_ancestors(self, uniprot):
        """
        For a UniProt ID returns its annotations including lowest level
        terms and their ancestors from all aspects of Gene Ontology.
        Returns set.
        """
        
        return self.all_full[uniprot] if uniprot in self.all_full else set()
    
    
    def has_term(self, uniprot, term):
        """
        Tells if an UniProt ID is annotated with a GO term.
        """
        
        return uniprot in self.all_full and term in self.all_full[uniprot]
    
    
    def has_any_term(self, uniprot, terms):
        """
        Tells if an UniProt ID is annotated with any of a set of GO terms.
        """
        
        return uniprot in self.all_full and term & self.all_full[uniprot]
    
    
    def all_uniprots(self):
        """
        Returns all UniProt IDs having annotations.
        """
        
        return set.union(*(
            set(getattr(self, asp.lower()).keys())
            for asp in self.aspects
        ))
    
    
    def i_select_by_term(self, term, uniprots = None):
        """
        Accepts a list of UniProt IDs and one or more gene ontology terms
        and returns a set of indices of those UniProts which are annotated
        with any of the terms.
        If no UniProts given all annotated UniProts considered.
        
        :param str,set term:
            A single GO term or set of terms.
        """
        
        uniprots = uniprots or sorted(self.all_uniprots())
        
        method = self.has_any_term if isinstance(term, set) else self.has_term
        
        return set(
            i
            for i, uniprot in enumerate(uniprots)
            if method(uniprot, term)
        )
    
    
    def select_by_name(self, name, uniprots = None, return_uniprots = False):
        """
        Accepts a list of UniProt IDs and one or more gene ontology names
        and returns the UniProts which are annotated with any of the names.
        If no UniProts given all annotated UniProts returned.
        
        :param str,set name:
            A single GO term name or set of names.
        :param bool return_uniprots:
            By default returns list of indices; if ``True`` returns a set of
            the selected UniProt IDs.
        """
        
        if isinstance(name, basestring):
            
            term = self.ontology.get_term(name)
            
        else:
            
            term = set(i[0] for i in self.ontology.names_to_terms(name))
        
        return self.select(
            term,
            uniprots = uniprots,
            return_uniprots = return_uniprots,
        )
    
    
    def select_by_term(self, term, uniprots = None):
        """
        Accepts a list of UniProt IDs and one or more gene ontology terms
        and returns the UniProts which are annotated with any of the terms.
        If no UniProts given all annotated UniProts returned.
        
        :param str,set term:
            A single GO term or set of terms.
        """
        
        uniprots = uniprots or sorted(self.all_uniprots())
        
        return set(
            numpy.array(uniprots)[
                list(self.i_select_by_term(uniprots, term))
            ]
        )
    
    
    def select_by_expr(
            self,
            expr,
            uniprots = None,
            return_uniprots = False,
        ):
        
        """
        Selects UniProts based on an expression of Gene Ontology terms.
        Operator precedence not considered, please use parentheses.
        Return indices of the selected elements in the ``uniprots`` list
        or the set of selected UniProt IDs.
        
        :param str expr:
            An expression of Gene Ontology terms. E.g.
            ``'(GO:0005576 and not GO:0070062) or GO:0005887'``. Parentheses
            and operators ``and``, ``or`` and ``not`` can be used.
        :param bool return_uniprots:
            By default returns list of indices; if ``True`` returns a set of
            the selected UniProt IDs.
        """
        
        ops = {
            'and': 'intersection',
            'or':  'union',
        }
        
        # if no UniProts provided does not make sense to return indices
        return_uniprots = return_uniprots or uniprots is None
        
        uniprots = uniprots or sorted(self.all_uniprots())
        
        if isinstance(expr, basestring):
            
            # tokenizing expression if it is a string
            # (method is recursive)
            expr = _rego.findall(expr)
        
        # initial values
        result   = set()
        stack    = []
        sub      = False
        negate   = False
        op       = None
        this_set = None
        
        for it in expr:
            
            # processing expression by tokens
            
            # we are in a sub-selection part
            if sub:
                
                if it == ')':
                    
                    # token is a closing parenthesis
                    # execute sub-selection
                    this_set = self.select_by_expr(
                        expr = stack,
                        uniprots = uniprots,
                    )
                    # empty stack
                    stack = []
                
                else:
                    
                    # token is something else
                    # add to sub-selection stack
                    stack.append(it)
                
            # we do actual processing of the expression
            elif it == 'not':
                
                # token is negation
                # turn on negation for the next set
                negate = True
                continue
                
            # open a sub-selection part
            elif it == '(':
                
                # token is a parenthesis
                # start a new sub-selection
                sub = True
                continue
                
            elif it[:3] == 'GO:':
                
                # token is a GO term
                # get the vertex selection by the single term method
                this_set = self._select_by_go(it)
                
                if negate:
                    
                    # take the inverse of the current set
                    this_set = set(xrange(len(uniprots))) - this_set
                    # set negation again to False
                    negate = False
                
            elif it in ops:
                
                # token is an operator
                # set it for use at the next operation
                op = ops[it]
            
            # we found a set
            if this_set is not None:
                
                # and an operator
                if op is not None:
                    
                    result = getattr(result, op)(this_set)
                
                # this normally happens only at the first set
                else:
                    
                    result = this_set
                
                this_set = None
                op       = None
        
        return self._uniprot_return(result, uniprots, return_uniprots)
    
    
    def select(self, terms, uniprots = None, return_uniprots = False):
        """
        Retrieves the UniProt IDs annotated with any Gene Ontology terms or
        their descendants, or evaluates string expression
        (see ``select_by_expr``).
        Returns indices of the selected elements in the ``uniprots`` list
        or the set of selected UniProt IDs.
        
        :param str,set terms:
            A single GO term, a set of GO terms or an expression with
            GO terms.
        :param bool return_uniprots:
            By default returns list of indices; if ``True`` returns a set of
            the selected UniProt IDs.
        """
        
        return_uniprots = return_uniprots or uniprots is None
        
        uniprots = uniprots or sorted(self.all_uniprots())
        
        # this is not an individual term but an expression
        if isinstance(terms, basestring) and len(terms) > 10:
            
            result = self.select_by_expr(terms, uniprots = uniprots)
            
        # either one term or a set of terms
        else:
            
            result = self.i_select_by_term(terms, uniprots = uniprots)
        
        return self._uniprot_return(result, uniprots, return_uniprots)
    
    
    def select_by_all(self, terms, uniprots = None, return_uniprots = False):
        """
        Selects the nodes annotated by all GO terms in ``terms``.
        
        Returns indices of the selected elements in the ``uniprots`` list
        or the set of selected UniProt IDs.
        
        :param list terms:
            List, set or tuple of GO terms.
        :param bool return_uniprots:
            By default returns list of indices; if ``True`` returns a set of
            the selected UniProt IDs.
        """
        
        return_uniprots = return_uniprots or uniprots is None
        
        uniprots = uniprots or sorted(self.all_uniprots())
        
        idx = set.intersection(*[self.select_by_term(term) for term in terms])
        
        return self._uniprot_return(result, uniprots, return_uniprots)
    
    
    def _uniprot_return(self, idx, uniprots, return_uniprots):
        
        if return_uniprots:
            
            return set(np.array(uniprots)[list(idx)])
        
        return idx


def annotate(graph, organism = 9606, aspects = ('C', 'F', 'P')):
    """
    Adds Gene Ontology annotations to the nodes of a graph.
    
    :param igraph.Graph graph:
        Any ``igraph.Graph`` object with uniprot IDs
        in its ``name`` vertex attribute.
    """
    
    aspects = aspects if type(aspects) in {list, tuple} else (aspects, )
    
    graph.vs['go'] = [
        {'C': set(), 'F': set(), 'P': set()}
        for _ in xrange(graph.vcount())
    ]
    
    terms, annot = dataio.go_annotations_goa(organism = organism)
    
    prg = progress.Progress(graph.vcount(), 'Loading GO annotations', 9)
    
    for v in graph.vs:
        
        prg.step()
        
        for asp in aspects:
            
            if v['name'] in annot[asp]:
                
                v['go'][asp] = annot[asp][v['name']]
    
    prg.terminate()


# old name as synonym
load_go = annotate
