import numpy as np, sys, time, inspect, os, pickle
from scipy.optimize import curve_fit

def create_subregion_queue_from_location(x, y, z, lx, ly, lz, rc, Nboxes=10):
    dx = lx/Nboxes; dy = ly/Nboxes; dz = lz/Nboxes
    
    x_index = (x%lx)//dx; y_index = (y%ly)//dy; z_index = (z%lz)//dz

    xmax = x+rc; xmin = x-rc; 
    ymax = y+rc; ymin = y-rc; 
    zmax = z+rc; zmin = z-rc; 
    
    xmax_index = int((xmax%lx)//dx); xmin_index = int((xmin%lx)//dx); 
    ymax_index = int((ymax%ly)//dy); ymin_index = int((ymin%ly)//dy); 
    zmax_index = int((zmax%lz)//dz); zmin_index = int((zmin%lz)//dz); 

    x_indices = []
    while x_index != (xmax_index+1)%Nboxes:
            x_indices.append(int(x_index)); x_index=(x_index+1)%Nboxes

    y_indices = []
    while y_index != (ymax_index+1)%Nboxes:
        y_indices.append(int(y_index)); y_index=(y_index+1)%Nboxes

    z_indices = []
    while z_index != (zmax_index+1)%Nboxes:
            z_indices.append(int(z_index)); z_index=(z_index+1)%Nboxes

    x_index = (x%lx)//dx; y_index = (y%ly)//dy; z_index = (z%lz)//dz

    while int(x_index) != (xmin_index-1)%Nboxes:
        x_indices.append(int(x_index)); x_index=(x_index-1)%Nboxes

    while y_index != (ymin_index-1)%Nboxes:
        y_indices.append(int(y_index)); y_index = (y_index-1)%Nboxes 

    while int(z_index) != (zmin_index-1)%Nboxes:
        z_indices.append(int(z_index)); z_index = (z_index-1)%Nboxes

    return make_three_tuples(set(x_indices), set(y_indices), set(z_indices))

def collect_atoms_in_cluster_distribution_from_directory(directory):
    atoms_in_cluster_distribution = []

    # List all .pkl files in the directory
    pkl_files = [f for f in os.listdir(directory) if f.endswith('.pkl')]

    for pkl_file in pkl_files:
        file_path = os.path.join(directory, pkl_file)
        
        # Load the pickle file
        with open(file_path, 'rb') as file:
            frame_dict = pickle.load(file)

        # Extract the atoms_in_cluster values
        for frame_number, clusters in frame_dict.items():
            for cluster_number, (atoms_in_cluster, _) in clusters.items():
                atoms_in_cluster_distribution.append(atoms_in_cluster)

    return atoms_in_cluster_distribution

def atomic_number_to_element(atomic_number):
    periodic_table = {1: 'H', 6: 'C', 8: 'O', 7: 'N', 16: 'S'}  # Extend this dictionary as needed
    return periodic_table.get(atomic_number, 'X')

def make_three_tuples(n1s, n2s, n3s):
    # Inputs: 
    #   - ns: integers
    # Outputs:
    #   - List of tuples (a, b, c) for all a in [n1min, n1max), [n2min, n2max), [n3min, n3max)
    # Example: make_three_tuple([1,2,3], [3,4], [6,8]) = [[1,3,6], [1,3,8], [1,4,6],...]

    triples = []
    for i in n1s:
        for j in n2s:
            for k in n3s:
                triples.append((i,j,k))

    return triples

def distance(a, b):
        return np.sqrt((a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2)

def extract_clusters_from_frame(frames, dump_path, rc, frame_numbers):
    lx, ly, lz = get_box_lengths_from_dump_file(dump_path=dump_path)

    clusters_by_frames = {}; cluster_index = 1; clusters = {}; current_cluster = []; reference_atoms=[]; queue1 = []; queue2 = []; clusters_by_frames = {}

    for N in frame_numbers:
        unclustered_atoms=frames[N].copy(); 
        while unclustered_atoms!={i:[] for i in frames[N].keys()}:
            remaining_molecules = []
            for i in unclustered_atoms.keys():
                for j in range(len(unclustered_atoms[i])):
                    remaining_molecules.append(unclustered_atoms[i][j][2])
            remaining_molecules=set(remaining_molecules)

            reference_molecule=min(remaining_molecules)
            for i in list(unclustered_atoms.keys()):
                for j in range(len(unclustered_atoms[i])):
                    if unclustered_atoms[i][j][2]==reference_molecule:
                        reference_atoms.append((i,unclustered_atoms[i][j])) 
                        queue1.append((i, unclustered_atoms[i][j]))
                        current_cluster.append((i, unclustered_atoms[i][j]))

            for i in queue1:
                unclustered_atoms[i[0]].remove(i[1])

            while queue1!=[]:
                for i in range(len(queue1)): 
                    # For every atom that is within rc of some atom on the reference molecule, search for other atoms that are within rc of it (but not on the reference molecule)
                    x, y, z = queue1[0][1][3:] 
                    search_subregions = create_subregion_queue_from_location(x, y, z, lx, ly, lz, rc)
                    for subregion in search_subregions:
                        for atom in unclustered_atoms[subregion]:
                            if distance(atom[3:], (x, y, z)) < rc:
                                for j in list(unclustered_atoms.keys()):
                                    for k in unclustered_atoms[j]:
                                        if k[2]==atom[2]:
                                            queue2.append((j,k))
                                            unclustered_atoms[j].remove(k)
                    queue1.remove(queue1[0])

                for atom in queue2:
                    if atom not in queue1:
                        queue1.append(atom)
                        current_cluster.append(atom)
                
                queue2=[]

            clusters[cluster_index]=(len(current_cluster), current_cluster)
            current_cluster=[]; cluster_index+=1 

        sorted_clusters = dict(sorted(clusters.items(), key=lambda item: item[1][0], reverse=True))
        clusters_by_frames[N]=sorted_clusters

    with open('../pickle_files/frames_'+str(min(frame_numbers))+'_'+str(max(frame_numbers))+'_clusters.pkl','rb') as doc:
        pickle.dump(clusters_by_frames, doc)

    return clusters_by_frames

def map_position_into_box_index(x, y, z, lx, ly, lz, Nboxes):
    dx = lx/Nboxes; dy = ly/Nboxes; dz = lz/Nboxes
    x = int(x//dx); y = int(y//dy); z = int(z//dz)
    return (x, y, z)

def distance_with_pbc(a, b, lx, ly, lz):
    # Inputs:
    #   - a and b are 3-tuples/lists that contain the positions to be wrapped are input coordinates to be wrapped
    #   - lx, ly, lz are box lengths

    # Outputs:
    #   - distance (float) between points a and b with respect to the minimum image convention for the given pbcs.

    dx = b[0] - a[0]; 
    if dx < -lx/2:
        dx+=lx
    elif dx >= lx/2:
        dx-=lx

    dy = b[1] - a[1]
    if dy < -ly/2:
        dy+=ly
    elif dy >= ly/2:
        dy-=ly

    dz = b[2] - a[2]
    if dz < -lz/2:
        dz+=lz
    elif dz >= lz/2:
        dz-=lz
    return np.sqrt(dx**2 + dy**2 + dz**2)

def wrap_coordinates_into_box(x, y, z, lx, ly, lz, x0=0, y0=0, z0=0):
    # Inputs:
    #   - x, y, z are input coordinates to be wrapped
    #   - lx, ly, lz are box lengths
    #   - x0, y0, z0 are usually the origin, but if your box is not at the origin, input the corner closest to the origin

    # Outputs:
    #   - x, y, and z locations after the point has been wrapped onto the box

    x=((x-x0)%lx)+x0; y=(y-y0)%ly+y0; z=(z-z0)%lz+z0
    return (x, y, z)

def get_box_lengths_from_dump_file(dump_path):

# Designed to read in only minimal portion of dump file.
    
    lines=[]
    with open(dump_path) as dump_file:
        for _ in range(5):
            next(dump_file)
        for _ in range(3):
            line = dump_file.readline(); lines.append(line.strip().split())
        x1, x2 = np.array(lines[0], dtype=float); lx = x2-x1
        y1, y2 = np.array(lines[1], dtype=float); ly = y2-y1
        z1, z2 = np.array(lines[2], dtype=float); lz = z2-z1
    return (lx, ly, lz)

def fit_data_to_line(x, y, xmin, xmax, p0, horizontal = False):
    if horizontal == False:
        x = np.array(x)
        params, covs = curve_fit(line, x[(x >= xmin) & (x <= xmax)], y[(x >= xmin) & (x <= xmax)], p0=p0)
        return params, covs
    
    if horizontal == True:
        x = np.array(x)
        params, covs = curve_fit(horizontal_line, x[(x >= xmin) & (x <= xmax)], y[(x >= xmin) & (x <= xmax)], p0=p0)
        return params, covs
    
def horizontal_line(x, b):
    return b

def line(x, m, b):
    return m*x+b