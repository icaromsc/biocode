import re
import biothings
import bioannotation
import sys
from urllib.parse import unquote, quote

def build_column_9( id=None, parent=None, other=None ):
    ## either the id or parent must be defined
    if id is None and parent is None:
        raise Exception("ERROR: attempt to build a GFF3 9th column with no ID or Parent attributes")

    colstring = None

    ## ID should always be first, if there is one
    if id is not None:
        colstring = "ID={0}".format(id)

    if parent is not None:
        if colstring is not None:
            colstring += ";"

        colstring += "Parent={0}".format(parent)

    # other is a dict of key,value pairs
    if other is not None:
        for att in other:
            if other[att] is not None:
                if colstring is not None:
                    colstring += ";"

                colstring += "{0}={1}".format(att, escape(other[att]))

    return colstring


def build_column_9_from_dict( atts ):
    """
    Accepts a dict of key/value pairs to print in column 9 and joins them
    into a single string, taking care to print the ID first, then Parent, if present.
    """
    colstring = ''

    if 'ID' in atts:
        colstring = "ID={0}".format(atts['ID'])
        del atts['ID']

    if 'Parent' in atts:
        if len(colstring) > 0:
            colstring += ';'

        colstring += "Parent={0}".format(atts['Parent'])
        del atts['Parent']

    # now print the rest
    for att in atts:
        if len(colstring) > 0:
            colstring += ';'

        colstring += "{0}={1}".format(att, escape(atts[att]))

    return colstring


def order_column_9(colstring):
    c9 = column_9_dict(colstring)
    colstring = build_column_9_from_dict(c9)
    return colstring


def set_column_9_value(colstring, key, val):
    """
    Pass a column 9 string and you can either set or update an existing
    value for it.  The full column 9 string is returned.
    """
    c9 = column_9_dict(colstring)
    c9[key] = val
    return build_column_9_from_dict(c9)



def column_9_dict(colstring):
    '''
    This was borrowed from the URL below and then modified for Python 3
    ftp://ftp.informatics.jax.org/%2Fpub/mgigff/gff3.py
    '''
    SEMI	= ';'
    COMMA	= ','
    EQ	        = '='
    WSP_RE = re.compile(r'^\s*$')

    if colstring == ".":
        return {}
    c9 = {}
    for t in colstring.split(SEMI):
        if WSP_RE.match(t):
            continue
        tt = t.split(EQ)
        if len(tt) != 2:
            raise Exception("Bad column 9 format: {0}".format(colstring) )
        n = unquote(tt[0].strip())
        [*v] = map(unquote, tt[1].strip().split(COMMA))
        if len(v) == 1:
            v = v[0]
        c9[n] = v

    return c9


def column_9_value(value, key):
    '''
    Pass a case-sensitive key and this function will return the value,
    if present, else None.

    This was borrowed from the URL below and then modified for Python 3
    ftp://ftp.informatics.jax.org/%2Fpub/mgigff/gff3.py
    '''
    SEMI	= ';'
    COMMA	= ','
    EQ	        = '='
    WSP_RE = re.compile(r'^\s*$')

    if value == ".":
        return {}
    c9 = {}
    for t in value.split(SEMI):
        if WSP_RE.match(t):
            continue
        tt = t.split(EQ)
        if len(tt) != 2:
            raise Exception("Bad column 9 format: {0}".format(value) )
        n = unquote(tt[0].strip())
        [*v] = map(unquote, tt[1].strip().split(COMMA))
        if len(v) == 1:
            v = v[0]
        c9[n] = v

    if key in c9:
        # this is a list if there were comma-separated values
        return c9[key]
    else:
        return None


def escape(s):
    """
    ;  =>  %3B
    =  =>  %3D
    &  =>  %26
    ,  =>  %2C
    """
    # before the comma-based one can be used build_column_9 needs to be able to
    #  support list values for 'other' attributes
    #return ''.join(x if x not in ';=&,' else quote(x) for x in s)
    return ''.join(x if x not in ';=&' else quote(x) for x in s)


def unescape(s):
    """
    %3B  =>  ;
    %3D  =>  =
    %26  =>  &
    %2C  =>  ,
    """
    return unquote(s)


def get_gff3_features(gff3_file, assemblies=None):
    '''
    Parses the passed GFF3 file and returns two dicts, loaded with biocode.biothings objects:

    1. The first dict are the Assembly objects, keyed on assembly ID.  Each Assembly has all of the
       children populated, so you can fully recover gene, RNA, exon and CDS features iterating on
       the assembly.
    2. The second dist is a flat structure of all the descendent feature objects of the Assemblies
       keyed by the feature IDs.

    See the documentation for each feature type in biocode.biothings for more info
    '''

    if assemblies is None:
        assemblies = dict()

    features   = dict()

    # these are related to parsing any embedded FASTA
    in_fasta_section = False
    is_assembly_fasta = False
    current_fasta_id = None
    lnum = 0
    FASTA_RE = re.compile(r'^\#\#FASTA\s*$')

    for line in open(gff3_file):
        lnum = lnum + 1
        #print("INFO: processing line: {0}".format(line) + " in_fasta_section=" + str(in_fasta_section))

        if in_fasta_section == True:
            m = re.search('>(\S+)\s*(.*)', line)
            if m:
                current_fasta_id = m.group(1)

                if current_fasta_id in assemblies:
                    is_assembly_fasta = True
                else:
                    is_assembly_fasta = False

            else:
                if current_fasta_id is None:
                    if (len(str(line.rstrip())) > 0):
                        raise Exception("FASTA parse error - sequence appears without preceding fasta id at line " + str(lnum))
                if is_assembly_fasta == True:
                    # must be a sequence line for an assembly
                    # python 2.6+ makes string concatenation amortized O(n)
                    #  http://stackoverflow.com/a/4435752/1368079
                    assemblies[current_fasta_id].residues += str(line.rstrip())
                    assemblies[current_fasta_id].length = len( assemblies[current_fasta_id].residues )

            continue

        elif FASTA_RE.match(line):
            # all data to the end of the file must be FASTA
            in_fasta_section = True
            continue

        # ignore all other comments
        if line.startswith('#'):
            continue

        cols = line.split("\t")

        if len(cols) != 9:
            continue

        mol_id = cols[0]

        # initialize this assembly if we haven't seen it yet
        if mol_id not in assemblies:
            assemblies[mol_id] = biothings.Assembly( id=mol_id, residues='' )

        current_assembly = assemblies[mol_id]
        rfmin = int(cols[3]) - 1
        rfmax = int(cols[4])
        rstrand = None
        atts = column_9_dict(cols[8])
        feat_id = atts.get('ID')
        parent_id = atts.get('Parent')
        parent_feat = None

        # sanity check
        if rfmin > rfmax:
            raise Exception("ERROR: Coordinates in GFF for feature id {0} appear to be reversed and violate GFF3 specification: {1} > {2}".format(feat_id, cols[3], cols[4]))

        if 'locus_tag' in atts:
            locus_tag = atts['locus_tag']
        else:
            locus_tag = None

        # shared features is not yet supported
        if isinstance(parent_id, list):
            raise Exception("This line contains a shared feature with multiple parents.  This isn't yet supported:\n{0}".format(line))

        if parent_id is not None:
            if parent_id in features:
                parent_feat = features[parent_id]
            else:
                raise Exception("Error in GFF3: Parent {0} referenced by a child feature before it was defined".format(parent_id) )

        if cols[6] == '-':
            rstrand = -1
        elif cols[6] == '+':
            rstrand = 1
        else:
            rstrand = 0

        phase = cols[7]

        if cols[2] == 'gene':
            gene = biothings.Gene(id=feat_id, locus_tag=locus_tag)
            gene.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            features[feat_id] = gene
            current_assembly.add_gene(gene)

        elif cols[2] == 'mRNA':
            mRNA = biothings.mRNA(id=feat_id, parent=parent_feat, locus_tag=locus_tag)
            mRNA.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_mRNA(mRNA)
            features[feat_id] = mRNA

        elif cols[2] == 'rRNA':
            rRNA = biothings.rRNA(id=feat_id, parent=parent_feat, locus_tag=locus_tag)
            rRNA.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_rRNA(rRNA)
            features[feat_id] = rRNA

        elif cols[2] == 'tRNA':
            tRNA = biothings.tRNA(id=feat_id, parent=parent_feat, locus_tag=locus_tag)
            tRNA.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_tRNA(tRNA)
            features[feat_id] = tRNA

        elif cols[2] == 'exon':
            exon = biothings.Exon(id=feat_id, parent=parent_feat)
            exon.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_exon(exon)
            features[feat_id] = exon

        elif cols[2] == 'CDS':
            if phase == '.':
                phase = 0
            else:
                phase = int(phase)

            CDS = biothings.CDS(id=feat_id, parent=parent_feat, phase=phase)
            CDS.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand, phase=phase)
            parent_feat.add_CDS(CDS)
            features[feat_id] = CDS

        elif cols[2] == 'polypeptide':
            polypeptide = biothings.Polypeptide(id=feat_id, parent=parent_feat)
            polypeptide.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_polypeptide(polypeptide)
            polypeptide.annotation = parse_annotation_from_column_9(cols[8])
            features[feat_id] = polypeptide

        elif cols[2] == 'five_prime_UTR':
            utr = biothings.FivePrimeUTR(id=feat_id, parent=parent_feat)
            utr.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_five_prime_UTR(utr)
            features[feat_id] = utr

        elif cols[2] == 'three_prime_UTR':
            utr = biothings.ThreePrimeUTR(id=feat_id, parent=parent_feat)
            utr.locate_on(target=current_assembly, fmin=rfmin, fmax=rfmax, strand=rstrand)
            parent_feat.add_three_prime_UTR(utr)
            features[feat_id] = utr

        else:
            sys.stderr.write( "Skipping feature {0} with type {1}\n".format(feat_id, cols[2]) )
            continue

        features[feat_id].length = rfmax - rfmin

    return (assemblies, features)


def parse_annotation_from_column_9(col9):
    annot = bioannotation.FunctionalAnnotation()
    atts = column_9_dict(col9)

    if 'product_name' in atts:
        annot.product_name = atts['product_name']

    if 'Dbxref' in atts:
        ec_nums = list()
        
        if isinstance(atts['Dbxref'], str) and atts['Dbxref'].startswith("EC"):
            ec_nums.append(atts['Dbxref'])
        else:
            for dbxref in atts['Dbxref']:
                if dbxref.startswith("EC"):
                    ec_nums.append(dbxref)

        for ec_num in ec_nums:
            ec_annot = bioannotation.ECAnnotation(number=ec_num)
            annot.add_ec_number(ec_annot)
    
    if 'Ontology_term' in atts:
        ont_terms = list()

        if isinstance(atts['Ontology_term'], str) and atts['Ontology_term'].startswith("GO"):
            ont_terms.append(atts['Ontology_term'])
        else:
            for term in atts['Ontology_term']:
                if term.startswith("GO"):
                    ont_terms.append(term)
        
        for go_id in ont_terms:
            go_annot = bioannotation.GOAnnotation(go_id=go_id)
            annot.add_go_annotation(go_annot)

        
        
    return annot

def parse_gff3_by_relationship( gff3_file ):
    '''
    Parses a GFF3 file, caring only about the ID/Parent relationships and returning a dict where
    they keys are the feature IDs and the values are an dict of dicts.   The depth of this depends
    on the depth of parent/child relationships, but every node looks like this:

    $feat_id = { children: [], fmin: 30, cols: [] }

    Every feature must have either and ID or Parent defined, else an error will be thrown.

    The structure returned looks like this:
    {
    $molecule_id = {
                         fmin: 30,
                         cols: [...],
                         children: {
                             same as this structure
                         }

                   }, ...


    }

    WARNING:
    This will currently fail on any GFF that:
       - allows the same IDs on multiple lines, such as those for  discontiguous features (allowed in spec)
       - features with shared parents


    '''
    ## might try turning this into a defaultdict at a later point: http://ohuiginn.net/mt/2010/07/nested_dictionaries_in_python.html
    fgraph = dict()
    current_molecule_id = None
    ## key = id, value = parent_id
    parentage = dict()
    ## where features go during processing that have a parent which hasn't been seen yet
    purgatory = list()

    for line in open(gff3_file):
        cols = line.split("\t")

        if len(cols) == 9:
            cols[8] = cols[8].rstrip()
        else:
            continue

        mol_id = cols[0]
        id = column_9_value(cols[8], 'ID')
        # shared parents will cause failure here
        parent = column_9_value(cols[8], 'Parent')

        if id:
            parentage[id] = parent

        if mol_id != current_molecule_id:
            if current_molecule_id is not None:
                _reunite_children( fgraph, current_molecule_id, purgatory )

            ## reset for the next molecule
            purgatory = list()
            current_molecule_id = mol_id

            if current_molecule_id not in fgraph:
                fgraph[current_molecule_id] = dict()

        molecule = fgraph[current_molecule_id]

        if parent:
            uparent = _get_ultimate_parent( parentage, parent )
            molecule[uparent]['children'].append( {'id': id, 'cols': cols} )
        else:
            if id is None:
                raise Exception("ERROR: Encountered a line without a Parent or ID assigned: {0}".format(line))

            ## this shouldn't exist already
            if id in molecule:
                raise Exception("ERROR: found duplicate id ({0}) in input file".format(id) )

            molecule[id] = {'fmin': cols[3], 'children': list(), 'cols': cols}

    ## don't forget to handle the last one
    _reunite_children( fgraph, current_molecule_id, purgatory )

    return fgraph


def print_gff3_from_assemblies(assemblies=None, ofh=None):
    """
    Utility function to write a complete GFF3 file from a list() of biothings.Assembly objects
    """
    if type(ofh).__name__ != 'TextIOWrapper':
        ofh = sys.stdout #TextIOWrapper
    
    ofh.write("##gff-version 3\n")

    for assembly_id in assemblies:
        current_assembly = assemblies[assembly_id]
        
        for gene in assemblies[assembly_id].genes():
            rnas_found = 0
            mRNAs = gene.mRNAs()
            
            for mRNA in mRNAs:
                mRNA_loc = mRNA.location_on(current_assembly)
                rnas_found += 1

                if rnas_found > 1:
                    gene.remove_mRNA(mRNA)
                    
                    print("INFO: splitting mRNA off gene {0}".format(gene.id))
                    new_gene = biothings.Gene( id="{0}_{1}".format(gene.id, rnas_found) )
                    new_gene.locate_on(target=current_assembly, fmin=mRNA_loc.fmin, fmax=mRNA_loc.fmax, strand=mRNA_loc.strand)
                    new_gene.add_RNA(mRNA)
                    new_gene.print_as(fh=ofh, format='gff3')

            if len(mRNAs) > 1:
                gene_loc = gene.location_on(current_assembly)
                mRNA_loc = mRNAs[0].location_on(current_assembly)
                gene_loc.fmin = mRNA_loc.fmin
                gene_loc.fmax = mRNA_loc.fmax
                gene_loc.strand = mRNA_loc.strand

            gene.print_as(fh=ofh, format='gff3')
    
    


def print_biogene( gene=None, fh=None, source=None, on=None ):
    '''
    This method accepts a Gene object located on an Assembly object (from biothings.py) and prints
    the feature graph for that gene in GFF3 format, including the gene, mRNA, CDS and exon features.
    '''
    ## handle defaults
    if source is None:
        source = '.'

    if gene is None:
        raise Exception( "ERROR: The print_biogene() function requires a biogene to be passed via the 'gene' argument" );

    ## we can auto-detect the molecule if the user didn't pass one
    #   and if there's only one.
    if on is None:
        on = gene.location().on

    gene_loc = gene.location_on( on )
    strand = '0'

    if gene_loc.strand == 1:
        strand = '+'
    elif gene_loc.strand == -1:
        strand = '-'

    gene_annot_atts = dict()
    if gene.locus_tag is not None:
        gene_annot_atts['locus_tag'] = gene.locus_tag

    columns = ['.']*9
    columns[0:3] = [gene_loc.on.id, source, 'gene']
    columns[3:7] = [str(gene_loc.fmin + 1), str(gene_loc.fmax), '.', strand]
    columns[8] = build_column_9( id=gene.id, parent=None, other=gene_annot_atts )

    ## print the gene line
    fh.write( "\t".join(columns) + "\n" )

    ## modifications for the RNA
    for RNA in gene.RNAs():
        RNA_loc = RNA.location_on( on )

        if RNA_loc is None:
            raise Exception("ERROR: Expected RNA {0} to be located on {1} but it wasn't".format(RNA.id, on.id))

        rna_annot_atts = dict()
        if RNA.locus_tag is not None:
            rna_annot_atts['locus_tag'] = RNA.locus_tag

        columns[2] = RNA.__class__.__name__
        columns[3:5] = [str(RNA_loc.fmin + 1), str(RNA_loc.fmax)]
        columns[8] = build_column_9( id=RNA.id, parent=RNA.parent.id, other=rna_annot_atts )
        fh.write( "\t".join(columns) + "\n" )

        ## Write any 5' UTRs
        for utr in RNA.five_prime_UTRs():
            utr_loc = utr.location_on( on )

            if utr_loc is None:
                raise Exception("ERROR: Expected UTR {0} to be located on {1} but it wasn't".format(utr.id, on.id) )

            columns[2] = 'five_prime_UTR'
            columns[3:5] = [str(utr_loc.fmin + 1), str(utr_loc.fmax)]
            columns[7] = str(utr_loc.phase)
            columns[8] = build_column_9( id=utr.id, parent=utr.parent.id, other=None )
            fh.write( "\t".join(columns) + "\n" )

        ## handle each CDS for this mRNA
        for CDS in RNA.CDSs():
            CDS_loc = CDS.location_on( on )

            if CDS_loc is None:
                raise Exception("ERROR: Expected CDS {0} to be located on {1} but it wasn't".format(CDS.id, on.id) )

            columns[2] = 'CDS'
            columns[3:5] = [str(CDS_loc.fmin + 1), str(CDS_loc.fmax)]
            columns[7] = str(CDS_loc.phase)
            columns[8] = build_column_9( id=CDS.id, parent=RNA.id, other=None )
            fh.write( "\t".join(columns) + "\n" )

        columns[7] = '.'

        ## handle each exon for this RNA
        for exon in RNA.exons():
            exon_loc = exon.location_on( on )

            if exon_loc is None:
                raise Exception("ERROR: Expected exon {0} to be located on {1} but it wasn't".format(exon.id, on.id))

            columns[2] = 'exon'
            columns[3:5] = [str(exon_loc.fmin + 1), str(exon_loc.fmax)]
            columns[8] = build_column_9( id=exon.id, parent=RNA.id, other=None )
            fh.write( "\t".join(columns) + "\n" )

        # are there polypeptides?
        for polypeptide in RNA.polypeptides():
            ## HACK - we probably don't want to keep this
            polypeptide_loc = RNA_loc
            annot = polypeptide.annotation
            assertions = dict()
            dbxref_strs = list()
            ontology_strs = list()

            if annot is not None:
                if annot.product_name is not None:
                    assertions['product_name'] = annot.product_name

                if annot.gene_symbol is not None:
                    assertions['gene_symbol'] = annot.gene_symbol

                # should this construction be in build_column_9() instead?
                # this is treating each EC number as a string, but each should be an ECAnnotation object
                for ec in annot.ec_numbers:
                    dbxref_strs.append("EC:{0}".format(ec.number))

                for go in annot.go_annotations:
                    ontology_strs.append("GO:{0}".format(go.go_id))

                for dbxref in annot.dbxrefs:
                    dbxref_strs.append("{0}:{1}".format(dbxref.db, dbxref.identifier))

            if len(dbxref_strs) > 0:
                assertions['Dbxref'] = ",".join(dbxref_strs)

            if len(ontology_strs) > 0:
                assertions['Ontology_term'] = ",".join(ontology_strs)

            columns[2] = 'polypeptide'
            columns[3:5] = [str(polypeptide_loc.fmin + 1), str(polypeptide_loc.fmax)]
            columns[8] = build_column_9( id=polypeptide.id, parent=polypeptide.parent.id, other=assertions )
            fh.write( "\t".join(columns) + "\n" )

        ## Write any 5' UTRs
        for utr in RNA.three_prime_UTRs():
            utr_loc = utr.location_on( on )

            if utr_loc is None:
                raise Exception("ERROR: Expected UTR {0} to be located on {1} but it wasn't".format(utr.id, on.id) )

            columns[2] = 'three_prime_UTR'
            columns[3:5] = [str(utr_loc.fmin + 1), str(utr_loc.fmax)]
            columns[7] = str(utr_loc.phase)
            columns[8] = build_column_9( id=utr.id, parent=utr.parent.id, other=None )
            fh.write( "\t".join(columns) + "\n" )


def print_biomatch( match=None, fh=None, source=None, on=None, mode=None ):
    '''
    This method accepts a Match object located on an Assembly object (from biothings.py) and prints
    the feature graph for that gene in GFF3 format.  How this is printed depends on the mode passed,
    but both modes suggested by the GFF3 specification are supported.

    mode=parts : Default.  In this mode, only MatchPart segments are printed but each shares the
    ID of the parent Match feature to indicate aligned segments.  The type for each row is the
    value of the parent Match.subclass.

    mode=match_and_parts : In this mode, both Match and MatchPart features are printed, with
    parent/child relationships explicitly defined and no shared IDs among any of the features.
    '''
    ## handle defaults
    if source is None:
        source = '.'

    if mode is None:
        mode = 'parts'

    ## we can auto-detect the molecule if the user didn't pass one and if there's only one.
    if on is None:
        on = match.location().on

    match_loc = match.location_on( on )
    strand = '0'

    if match_loc.strand == 1:
        strand = '+'
    elif match_loc.strand == -1:
        strand = '-'

    if mode == 'match_and_parts':
        columns = ['.']*9
        columns[0:3] = [match_loc.on.id, source, match.subclass]
        columns[3:7] = [str(match_loc.fmin + 1), str(match_loc.fmax), '.', strand]
        columns[8] = build_column_9( id=match.id, parent=None, other=None )
        fh.write( "\t".join(columns) + "\n" )

    for mp in match.parts:
        columns = ['.']*9
        mp_loc = mp.location_on(on)
        columns[3:7] = [str(mp_loc.fmin + 1), str(mp_loc.fmax), '.', strand]

        if mode == 'parts':
            columns[0:3] = [mp_loc.on.id, source, match.subclass]
            columns[8] = build_column_9( id=match.id, parent=None, other=None )
        elif mode == 'match_and_parts':
            columns[0:3] = [mp_loc.on.id, source, 'match_part']
            columns[8] = build_column_9( id=mp.id, parent=match.id, other=None )

        fh.write( "\t".join(columns) + "\n" )


def _reunite_children( fg, mol_id, kids ):
    sys.stderr.write("WARNING: biocodegff._reunite_children called but not yet implemented.  You are ahead of your time.\n")
    pass


def _get_ultimate_parent( p, id ):
    if p is None:
        return id

    oldest = id

    while p[oldest] is not None:
        oldest = p[oldest]

    return oldest










