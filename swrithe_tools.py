from __future__ import print_function # Only Python 2.x
import numpy as np
import os,re
from PSIPREDauto.functions import single_submit
import shutil
import urllib
import biobox as bb
import biotite.structure as struc
import biotite.structure.io.mmtf as mmtf
import biotite.sequence as seq
import biotite.database.rcsb as rcsb
import plotly.graph_objects as go
import plotly.express as px
from tempfile import gettempdir
import statsmodels.nonparametric.smoothers_lowess as sm
from sklearn.cluster import DBSCAN
import subprocess


def get_pdb(pdb_code):
    if not os.path.isdir(os.getcwd()+'/molecules/'):
        os.mkdir(os.getcwd()+'/molecules/')
    # Fetch and load structure
    urllib.request.urlretrieve('http://files.rcsb.org/download/'+pdb_code+'.pdb', 'molecules/'+pdb_code+'.pdb')
    print('File saved to: '+'molecules/'+pdb_code+'.pdb')

def get_chains_from_biotite(pdb_code):
    # Fetch and load structure
    file_name = rcsb.fetch(pdb_code.upper(), "mmtf", gettempdir())
    mmtf_file = mmtf.MMTFFile.read(file_name)
    array = mmtf.get_structure(mmtf_file, model=1)
    array = array[struc.filter_amino_acids(array)]
    return struc.get_chains(array)    
    
def convert(s):
    new = ""
    for x in s:
        new+= x
    return new
    
def simple_ss_clean(fp):
    for i in range(len(fp)-1):
        if fp[i-1]==fp[i+1] and fp[i-1]!=fp[i]:
            fp[i]=fp[i-1]
    return convert(fp)

def get_all_edges(curve):
    edges=[]
    for i in range(1,len(curve)):
        edges.append([curve[i-1],curve[i]])
    return edges

def split(word):
    return [char for char in word]

def get_sses(ss):
    sses=[]
    count = 1
    i = 0
    while i<len(ss)-1:
        if ss[i+1] == ss[i]:
            count += 1
            i += 1
        else:
            sses.append([ss[i], count])
            count = 1
            i += 1
    sses.append([ss[-1], count])
    return sses

def intersect_line_triangle(q1,q2,p1,p2,p3):
    def signed_tetra_volume(a,b,c,d):
        return np.sign(np.dot(np.cross(b-a,c-a),d-a)/6.0)

    s1 = signed_tetra_volume(q1,p1,p2,p3)
    s2 = signed_tetra_volume(q2,p1,p2,p3)

    if s1 != s2:
        s3 = signed_tetra_volume(q1,q2,p1,p2)
        s4 = signed_tetra_volume(q1,q2,p2,p3)
        s5 = signed_tetra_volume(q1,q2,p3,p1)
        if s3 == s4 and s4 == s5:
            n = np.cross(p2-p1,p3-p1)
            t = np.dot(p1-q1,n) / np.dot(q2-q1,n)
            return True
    return False

def write_curve_to_file(curve,outfile_name):
    with open(outfile_name,'w+') as f:
        for i in range(len(curve)-1):
            string = ' '.join(map(str,curve[i]))
            f.write(string)
            f.write('\n')
        f.write(' '.join(map(str,curve[-1])))
        f.close()
        
def pdb_to_fasta(pdb_code,chain):
    pdb_file_loc=r'molecules/'+pdb_code+'.pdb'
    aa3to1={
   'ALA':'A', 'VAL':'V', 'PHE':'F', 'PRO':'P', 'MET':'M',
   'ILE':'I', 'LEU':'L', 'ASP':'D', 'GLU':'E', 'LYS':'K',
   'ARG':'R', 'SER':'S', 'THR':'T', 'TYR':'Y', 'HIS':'H',
   'CYS':'C', 'ASN':'N', 'GLN':'Q', 'TRP':'W', 'GLY':'G',
   'MSE':'M',
    }
    ca_pattern=re.compile("^ATOM\s{2,6}\d{1,5}\s{2}CA\s[\sA]([A-Z]{3})\s([\s\w])|^HETATM\s{0,4}\d{1,5}\s{2}CA\s[\sA](MSE)\s([\s\w])")
    filename=os.path.basename(pdb_file_loc).split('.')[0]
    chain_dict=dict()
    chain_list=[]
    fp=open(pdb_file_loc,'r')
    for line in fp.read().splitlines():
        if line.startswith("ENDMDL"):
            break
        match_list=ca_pattern.findall(line)
        if match_list:
            resn=match_list[0][0]+match_list[0][2]
            chain=match_list[0][1]+match_list[0][3]
            if chain in chain_dict:
                chain_dict[chain]+=aa3to1[resn]
            else:
                chain_dict[chain]=aa3to1[resn]
                chain_list.append(chain)
    fp.close()
    with open(pdb_file_loc[:-4]+'.fasta','w+') as fout:
        fout.write(chain_dict[chain])

def get_ss_fp_psipred(fasta_file_loc):
    dssp_to_simp = {"I" : "H",
                 "S" : "-",
                 "H" : "H",
                 "E" : "S",
                 "G" : "H",
                 "B" : "S",
                 "T" : "-",
                 "C" : "-"
                 }
    lines = []
    with open(fasta_file_loc+' output/'+os.path.splitext(os.path.basename(fasta_file_loc))[0]+'.ss','r') as fin:
        for line in fin:
            lines.append(line.split())
    ss = [dssp_to_simp[i[2]] for i in lines]
    return get_sses(simple_ss_clean(ss))

def get_ss_fp(fp_file_loc):
    with open(fp_file_loc,'r') as fin:
        for line in fin:
            ss=line.split()[0]
    return get_sses(ss)

def get_coords(pdb_file_loc,chain):
    M = bb.Molecule(pdb_file_loc)
    ca = M.atomselect(chain,'*','CA')
    return ca

def get_fasta_file(pdb_code):
    pdb_file_loc=r'molecules/'+pdb_code+'.pdb'
    single_submit(pdb_file_loc[:-4]+'.fasta', "foo@bar.com", '')

def skmt(pdb_code,chain):
    pdb_file_loc=r'molecules/'+pdb_code+'.pdb'
    pdb_to_fasta(pdb_code,chain)
    get_fasta_file(pdb_code)
    mol = get_coords(pdb_file_loc,chain)
    if not os.path.isfile(pdb_file_loc[:-4]+'.fasta'):
        pdb_to_fasta(pdb_file_loc,chain)
    if not os.path.isdir(pdb_file_loc[:-4]+'.fasta output/'):
        get_fasta_file(pdb_file_loc)
    ss = get_ss_fp_psipred(pdb_file_loc[:-4]+'.fasta')
    #shutil.rmtree(pdb_file_loc[:-4]+'.fasta output')
    splitcurve = []
    index = 0
    for i in ss:
        splitcurve.append(mol[index:index+i[1]])
        index+=i[1]
    newcurve = []
    for i in range(len(splitcurve)):
        for j in range(len(splitcurve[i])):
            newcurve.append(splitcurve[i][j])
    for subsec in range(len(splitcurve)):
        if len(splitcurve[subsec])>2:
            checks = []
            for idx in range(1,len(splitcurve[subsec])-1):
                p1 = 1.25*splitcurve[subsec][0]-splitcurve[subsec][1]
                p2 = splitcurve[subsec][idx]
                p3 = 1.25*splitcurve[subsec][-1]-splitcurve[subsec][-2]
                for edge in get_all_edges(newcurve):
                    q0 = edge[0]
                    q1 = edge[1]
                    checks.append(intersect_line_triangle(q0,q1,p1,p2,p3))
            if not any(checks):
                splitcurve[subsec] = [splitcurve[subsec][0]]
                newcurve = []
                for l in range(len(splitcurve)):
                    for m in range(len(splitcurve[l])):
                        newcurve.append(splitcurve[l][m])
            else:
                idx=2
                while idx<len(splitcurve[subsec]):
                    newcurve = []
                    for i in range(len(splitcurve)):
                        for j in range(len(splitcurve[i])):
                            newcurve.append(splitcurve[i][j])
                    p1 = splitcurve[subsec][idx-2]
                    p2 = splitcurve[subsec][idx-1]
                    p3 = splitcurve[subsec][idx]
                    checks = []
                    for edge in get_all_edges(newcurve):
                        q0 = edge[0]
                        q1 = edge[1]
                        checks.append(intersect_line_triangle(q0,q1,p1,p2,p3))
                    if not any(checks):
                        splitcurve[subsec] = np.delete(splitcurve[subsec],idx-1,axis=0)
                        idx=2
                    else:
                        idx+=1
        else:
            splitcurve[subsec] = [splitcurve[subsec][0]]
            newcurve = []
            for l in range(len(splitcurve)):
                for m in range(len(splitcurve[l])):
                    newcurve.append(splitcurve[l][m])
    newcurve = []
    for i in range(len(splitcurve)):
        for j in range(len(splitcurve[i])):
            newcurve.append(splitcurve[i][j])
    if not np.array_equal(newcurve[-1],mol[-1]):
        newcurve.append(mol[-1])
    write_curve_to_file(newcurve,pdb_file_loc[:-4]+'.xyz')
    return 'SKMT Curve is saved at ' + pdb_file_loc[:-4]+'.xyz'

def view_molecule_subset(molecule,start=0,end=-1):
    mol = np.genfromtxt(molecule)
    if end != -1:
        xs = mol[:,0][start:end]
        ys = mol[:,1][start:end]
        zs = mol[:,2][start:end]
    else:
        xs = mol[:,0][start:]
        ys = mol[:,1][start:]
        zs = mol[:,2][start:]
    fig = go.Figure(data=go.Scatter3d(
        x=xs, y=ys, z=zs,opacity=0.9,
        marker=dict(
            size=1,
            color=[i*100/len(xs) for i in range(len(xs))],
            colorscale='Rainbow'
        ),
        line=dict(
            width=10,
            color=[i*100/len(xs) for i in range(len(xs))],
            colorscale='Rainbow'
        ),))
    colorbar_trace = go.Scatter3d(x=[None],
                          y=[None], z=[None],
                          mode='markers',
                          marker=dict(
                              colorscale='Rainbow',
                              showscale=True,
                              cmin=-5,
                              cmax=5,
                              colorbar=dict(thickness=25, tickvals=[-5, 5], ticktext=['Start','End'], outlinewidth=0)
                          ),
                          hoverinfo='none'
                        )
    fig['layout']['showlegend'] = False
    fig.add_trace(colorbar_trace)
    fig.update_layout(width=1250,height=1000)
    fig.update_layout(
    scene=dict(
        xaxis_title='',
        yaxis_title='',
        zaxis_title='',
        aspectratio = dict( x=1, y=1, z=1 ),
        aspectmode = 'manual',
        xaxis = dict(
            gridcolor="white",
            showbackground=False,
            zerolinecolor="white",
            nticks=0,
            showticklabels=False),
        yaxis = dict(
            gridcolor="white",
            showbackground=False,
            zerolinecolor="white",
            nticks=0,
            showticklabels=False),
        zaxis = dict(
            gridcolor="white",
            showbackground=False,
            zerolinecolor="white",
            nticks=0,
            showticklabels=False),),
    )
    return fig.show()

def find_helical_sections(DI):
    x = DI[:,1]
    y = DI[:,2]
    hels = []
    lowess_tight = sm.lowess(y, x, frac = .15)   
    x = lowess_tight[:,0]
    y = lowess_tight[:,1]
    for i in range(len(y)-9):
        for j in range(i+9,len(y)):
            if abs((y[j]-y[i])/(j-i)) >= 0.1:
                signs = []
                for k in range(j-i):
                    signs.append(np.sign(y[i+k+1]-y[i+k]))
                if abs(sum(signs))==len(signs) or abs(sum(signs)) == len(signs)-2:
                    hels.append([i+5,j+5,(y[j]-y[i])/(j-i)])
    ranges = [[i[0],i[1]] for i in hels]
    starts = [i[0] for i in ranges]
    ends = [i[1] for i in ranges]
    overlapping_subsections = find_overlapping_subsections(ranges)
    res=[]
    for i in overlapping_subsections:
        lengths = [sec[1]-sec[0] for sec in i]
        tmp=[]
        for sec in i:
            if sec[1]-sec[0]==max(lengths):
                tmp.append(sec)
        if len(tmp)==0:
            continue
        elif len(tmp)==1:
              res.append(tmp[0])
        else:
              res.append([tmp[0][0],tmp[-1][1]])
    return res

def find_overlapping_subsections(intervals):
    if not intervals:
        return []

    intervals.sort(key=lambda x: x[0])
    result = []
    overlapping_subsection = [intervals[0]]

    for i in range(1, len(intervals)):
        current_start, current_end = intervals[i]
        prev_start, prev_end = overlapping_subsection[-1]

        if current_start <= prev_end:
            overlapping_subsection.append(intervals[i])
            prev_end = max(prev_end, current_end)
            overlapping_subsection[-1][1] = prev_end
        else:
            if len(overlapping_subsection) > 1:
                result.append(overlapping_subsection)
            overlapping_subsection = [intervals[i]]

    if len(overlapping_subsection) > 1:
        result.append(overlapping_subsection)

    return result

def measure_roadieness(wr_list_in):
    wr_list_whole = [item for item in wr_list_in if item[1] > item[0]]
    length = len(wr_list_whole)
    result = []
    for i in range(2, length):
        wr_list = wr_list_whole[:i]
        if len(wr_list) > 1:
            wr_list = [item[2] for item in wr_list]
            max_val = max(map(abs, wr_list))
            end_diff = wr_list[-1] - wr_list[0]
            result.append([wr_list_whole[i][0], wr_list_whole[i][1], max_val, end_diff])
        else:
            result.append([0, 0, 0.0, 0.0])
    return result

def retrieve_clusters(clustered_list):
    no_noise = [i for i in clustered_list if i[1]!=-1]
    res = defaultdict(list)
    for v, k in no_noise:
        res[k].append(v)
    returns = []
    for key in res.keys():
        returns.append(res[key][-1])
    max_length = max([i[1]-i[0] for i in returns])
    return [i for i in returns if i[1]-i[0]==max_length]

def find_roadie_sections(fp):
    rtests = measure_roadieness(np.genfromtxt(fp))
    pos = [i for i, item in enumerate(rtests) if item[2] > 0.95 and abs(item[3]) < 0.05]
    if len(pos) > 0:
        potential_secs = [rtests[i] for i in pos]
        uppers = list(set([item[1] for item in potential_secs]))
        bound_pairs = []
        for upper in uppers:
            max_lower = max([item[0] for item in potential_secs if item[1] == upper])
            bound_pairs.append([max_lower, upper])
        if len(bound_pairs) > 1:
            clus = [cluster for cluster in bound_pairs if cluster[1] - cluster[0] > 4]
            clustering = DBSCAN(eps=3, min_samples=1).fit_predict(clus)
            clustered = zip(clus,clustering)
            return retrieve_clusters(list(clustered))
        else:
            return []
    else:
        return []
    

def writhePlot(pdb_code,highlight_helical_subsections=False,highlight_roadie_subsections=False):
    colors = px.colors.sequential.dense
    if os.path.isfile("molecules/"+pdb_code+".dat"):
        fp = np.loadtxt("molecules/"+pdb_code+".dat")
        DI=fp[fp[:,0]==1]
        if highlight_helical_subsections:
            try:
                res1 = find_helical_sections(DI)
                colspace = np.linspace(0,10,len(res1)+2)[1:-1]
            except:
                print('No helical subsections')
                highlight_helical_subsections=False
        if highlight_roadie_subsections:
            try:
                res2 = find_roadie_sections(DI)
                colspace = np.linspace(0,10,len(res2)+2)[1:-1]
            except:
                print('No roadie subsections')
                highlight_roadie_subsections=False
        x = DI[:,1]
        y = DI[:,2]
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=x,y=y,mode='lines',name=pdb_code.upper(),marker=dict(color='black',size=10),
                             line=dict(width=5)))
        if highlight_helical_subsections:
            for i in range(len(res1)):
                stindex = np.where(x == res1[i][0])[0][0]
                endex = np.where(x==res1[i][1])[0][0]
                fig.add_trace(go.Scatter(x=x[stindex:endex],y=y[stindex:endex],
                                           mode='lines',
                                          name='Helical Subsection '+str(i+1),
                                          showlegend=True,
                                          marker=dict(color=colors[int(colspace[i])],size=10),
                                          line=dict(width=7.5)
                                        )
                )
        if highlight_roadie_subsections:
            for i in range(len(res2)):
                stindex = np.where(x == res2[i][0]+4)[0][0]
                endex = np.where(x==res2[i][1])[0][0]
                fig.add_trace(go.Scatter(x=x[stindex:endex],y=y[stindex:endex],
                                      mode='lines',
                                      name='Roadie Subsection '+str(i+1),
                                      showlegend=True,
                                      marker=dict(color=colors[int(colspace[i])],size=10),
                                      line=dict(width=7.5)
                                      )
                )

        fig.update_layout(
            autosize=False,
            width=1000,
            height=0.75*1000)
        fig.update_layout(
            font_family="Tenorite",
            font_color="black",
            title_font_family="Tenorite",
            title_font_color="black",
            legend_title_font_color="black",
            xaxis_title="Subsection Length",
            yaxis_title="Writhe",
            font=dict(size=28)
        )
        fig.update_layout(template='simple_white')
        fig.show()
    else: 
        print("you need to calculate the writhe finger print of this file first: run "+"calculate_writheFP(pdb_code)")
    
def calculate_writheFP(pdb_code):
    os.popen(r"getFingerPrint "+r"molecules/"+pdb_code+r".xyz"+r" "+r"molecules/"+pdb_code+r".dat")  
    

def view_molecule_helical(pdb_code):
    if os.path.isfile('molecules/'+pdb_code+'.xyz'):
        mol = np.genfromtxt('molecules/'+pdb_code+'.xyz')
        if os.path.isfile("molecules/"+pdb_code+".dat"):
            fp = np.loadtxt("molecules/"+pdb_code+".dat")
            DI=fp[fp[:,0]==1]
            res = find_helical_sections(DI)
            colors = px.colors.sequential.dense
            colspace = np.linspace(0,10,len(res)+2)[1:-1]

            x = mol[:,0]
            y = mol[:,1]
            z = mol[:,2]
            cols = ['black' for i in range(len(x))]
            for i in range(len(res)):
                stindex = np.where(DI[:,1] == res[i][0])[0][0]
                endex = np.where(DI[:,1]==res[i][1])[0][0]
                for j in range(stindex,endex):
                    cols[j] = colors[int(colspace[i])]
            fig = go.Figure()
            fig.add_trace(go.Scatter3d(
                x=x, y=y, z=z,
                marker=dict(
                    size=1,
                    color=cols
                ),
                line=dict(
                    width=15,
                    color=cols
                ),))
            fig['layout']['showlegend'] = False
            fig.update_layout(
            scene=dict(
                xaxis_title='',
                yaxis_title='',
                zaxis_title='',
                aspectratio = dict( x=1, y=1, z=1 ),
                aspectmode = 'manual',
                xaxis = dict(
                    gridcolor="white",
                    showbackground=False,
                    zerolinecolor="white",
                    nticks=0,
                    showticklabels=False),
                yaxis = dict(
                    gridcolor="white",
                    showbackground=False,
                    zerolinecolor="white",
                    nticks=0,
                    showticklabels=False),
                zaxis = dict(
                    gridcolor="white",
                    showbackground=False,
                    zerolinecolor="white",
                    nticks=0,
                    showticklabels=False),),
            )
            fig.update_layout(margin=dict(l=0, r=0, b=0, t=0))
            return fig.show()
        else:
            print("you need to calculate the writhe finger print of this file first: run "+"calculate_writheFP(pdb_code)")
    
    else:
        print("Smoothed kmt curve does not exist you must make it first: run sw.skmt(pdb_code,chain_id)")

        
def extract_nums(text):
    for item in text.split(' '):
        try:
            yield float(item)
        except ValueError:
            pass
        
def toPairs(compareLst):
    outLst = []
    for i in range(0,len(compareLst)-2,4):
        outLst.append([intLst(compareLst[i:i+2]),intLst(compareLst[i+2:i+4])])
    outLst.append([compareLst[-2],compareLst[-1]])
    return outLst

def intLst(list_of_floats):
    return [int(item) for item in list_of_floats]

def compare_prep(pdb_code):
    print('Preparing files for: '+pdb_code)
    get_pdb(pdb_code)
    chain_id=get_chains_from_biotite(pdb_code)[0]
    skmt(pdb_code,chain_id)
    calculate_writheFP(pdb_code)
    print('Files prepared for: '+pdb_code)
    

def compare_molecules(pdb_code1,pdb_code2,cutOff):
    if not os.path.isfile(r"molecules/"+pdb_code1+r".dat"):
        compare_prep(pdb_code1)
    if not os.path.isfile(r"molecules/"+pdb_code2+r".dat"):
        compare_prep(pdb_code2)
    get_data=subprocess.check_output(r"compareFingerPrints "+r"molecules/"+pdb_code1+r".xyz"+r" "+r"molecules/"+pdb_code2+r".xyz "+str(cutOff),shell=True, encoding='utf-8')
    return toPairs(list(extract_nums(get_data)))

def compare_database(pdb_code,cutOff=0.05):
    if not os.path.isdir(os.getcwd()+'/comparisons/'):
        os.mkdir(os.getcwd()+'/comparisons/')
    comstr = [r"compareToLibrary",r"molecules/"+pdb_code+r".xyz",r"data/CleanedKMT",str(cutOff),pdb_code]
    popen = subprocess.Popen(comstr, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line 
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)

def compareToDatabase(pdb_code,cutoff=0.05):
    for path in compare_database(pdb_code,cutoff):
        print(path,  end='\x1b[1K\r')
        
def data_for_cylinder_along_arb(center,tandirec,height_z,radius=0.8):
    z = np.linspace(0, height_z, int(height_z))
    theta = np.linspace(0, 2*np.pi,25)
    theta_grid, z_grid=np.meshgrid(theta, z)
    tperp = np.sqrt(tandirec[0]*tandirec[0] + tandirec[1]*tandirec[1])
    tperp2 =np.sqrt(4.0*tandirec[0]*tandirec[0]*tandirec[1]*tandirec[1] + tperp*tperp*tandirec[2]*tandirec[2])
    x_grid = -radius*tandirec[0]*np.cos(theta_grid)/tperp - radius*tandirec[1]*tandirec[2]*np.sin(theta_grid)/tperp2+ tandirec[0]*z_grid + center[0]
    y_grid = radius*tandirec[1]*np.cos(theta_grid)/tperp - radius*tandirec[0]*tandirec[2]*np.sin(theta_grid)/tperp2+ tandirec[1]*z_grid + center[1]
    z_grid = 2.0*radius*tandirec[0]*tandirec[1]*np.sin(theta_grid)/tperp2+ tandirec[2]*z_grid + center[2]
    return x_grid,y_grid,z_grid

def data_for_cylinder_along_z(center_x,center_y,radius,height_z):
    z = np.linspace(0, height_z, int(5*height_z))
    theta = np.linspace(0, 2*np.pi, 25)
    theta_grid, z_grid=np.meshgrid(theta, z)
    x_grid = radius*np.cos(theta_grid) + center_x
    y_grid = radius*np.sin(theta_grid) + center_y
    return x_grid,y_grid,z_grid

def plot_molecule_tube(pdb_code):
    file_loc = 'molecules/'+pdb_code+'.xyz'
    times = 25
    mol = np.genfromtxt(file_loc)
    Xc,Yc,Zc = data_for_cylinder_along_arb(mol[0],(mol[1]-mol[0])/np.linalg.norm(mol[1]-mol[0]),np.linalg.norm(mol[1]-mol[0]))
    for i in range(2,len(mol)):
        normalised_tangent =  (mol[i]-mol[i-1])/np.linalg.norm(mol[i]-mol[i-1])
        prev_normalised_tangent = (mol[i-1]-mol[i-2])/np.linalg.norm(mol[i-1]-mol[i-2])
        for j in range(1,times):
            cap_data = data_for_cylinder_along_arb(mol[i-1],
                                                   ((times-j)/(times-1))*prev_normalised_tangent + (j/(times-1))*normalised_tangent,
                                                   1,
                                                  )
            Xc = np.concatenate((Xc,cap_data[0]),axis=0)
            Yc = np.concatenate((Yc,cap_data[1]),axis=0)
            Zc = np.concatenate((Zc,cap_data[2]),axis=0)
        edge_data = data_for_cylinder_along_arb(mol[i-1],
                                                normalised_tangent,
                                                int(np.linalg.norm(mol[i]-mol[i-1]))
                                               )
        Xc = np.concatenate((Xc,edge_data[0]),axis=0)
        Yc = np.concatenate((Yc,edge_data[1]),axis=0)
        Zc = np.concatenate((Zc,edge_data[2]),axis=0)

    surcol = np.zeros((Zc-Zc[0]).shape)
    for i in range(len(surcol)):
        surcol[i] = i*np.ones(surcol[i].shape)
    lighting_effects = dict(ambient=0.5, diffuse=0.25, roughness = 0.9, specular=0.65, fresnel=1)
    fig = go.Figure()
    fig.add_trace(go.Surface(x=Xc, y=Yc, z=Zc,
                             showscale=False,
                             surfacecolor=surcol,
                             colorscale='Rainbow',
                             lighting=dict(lighting_effects),
                             lightposition=dict(x=1000,y=1000,z=1000),
                             hoverinfo='none'
                            )
                 )
    colorbar_trace = go.Scatter3d(x=[None],
                                  y=[None],
                                  z=[None],
                                  mode='markers',
                                  marker=dict(
                                      colorscale='Rainbow',
                                      showscale=True,
                                      cmin=surcol[0][0],
                                      cmax=surcol[-1][0],
                                      colorbar=dict(thickness=25, 
                                                    tickvals=[surcol[0][0],surcol[-1][0]], 
                                                    ticktext=['Start','End'],
                                                    outlinewidth=0)
                                  ),
                                  hoverinfo='none'
                                 )
    fig.add_trace(colorbar_trace)
    fig.update_layout(width=1000,height=1000)
    fig.update_layout(
    scene=dict(
        xaxis_title='',
        yaxis_title='',
        zaxis_title='',
        aspectratio = dict( x=1, y=1, z=1 ),
        aspectmode = 'manual',
        xaxis = dict(
            gridcolor="white",
            showbackground=False,
            zerolinecolor="white",
            nticks=0,
            showticklabels=False),
        yaxis = dict(
            gridcolor="white",
            showbackground=False,
            zerolinecolor="white",
            nticks=0,
            showticklabels=False),
        zaxis = dict(
            gridcolor="white",
            showbackground=False,
            zerolinecolor="white",
            nticks=0,
            showticklabels=False),),
    )
    fig.show()