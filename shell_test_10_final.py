
##############################################################################################################################
import opensees.openseespy as ops  # Import OpenSeesPy module
import numpy as np                  # For numerical operations (unused in this snippet)
import math                         # For floating-point comparisons
import csv                          # For writing CSV outputs
import os                           # For filesystem operations

############################
# Start of model generation#
############################

def create_model(walk_edge=False):
    # Create ModelBuilder: 3 dimensions, 6 DOF per node
    model = ops.Model(ndm=3, ndf=6)

    #E = 3.0e3  # Elastic modulus placeholder (kips/in^2)

    # Define materials and section
    # -------------------------------------------------------------------------------------------------------------------------------
    cover_1, rebar, total = 1.25, 1, 6
    core = total - 2*cover_1 - 2*rebar
    Econcr = 3600 #ksi

    linear = False
    if linear: 
        model.nDMaterial("ElasticIsotropic", 1, Econcr, 0.2) 
        model.uniaxialMaterial('Elastic', 2, 30000.0)
        
    else:
        model.eval(rf"""
            nDMaterial ASDConcrete3D 1 {Econcr} 0.2 \
            -Te 0.0 9e-05 0.00015 0.00507 0.0250501 0.250501 \
            -Ts 0.0   2.7     3.0     0.6 0.003 0.003 \
            -Td 0.0 0.0 0.0 0.960552268244576 0.9999800399998403 0.9999995660869531 \
            -Ce 0.0 0.0005 0.0006666666666666666 0.0008333333333333333 0.001 0.0011666666666666665 0.0013333333333333333 0.0015 0.0016666666666666666 0.0018333333333333333 0.002 0.18327272727272728 0.18377272727272728 \
            -Cs 0.0 15.0 19.282032302755088 22.459666924148337 24.852813742385703 26.6515138991168 27.979589711327122 28.92304845413264 29.54451150103322 29.891252930760572 30.0 3.0 3.0 \
            -Cd 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 -2.220446049250313e-16 0.0 0.0 0.9981618744961699 0.9981786141748574 \
            -autoRegularization 8.97663211186248
        """)

        model.uniaxialMaterial('Steel01', 2, 60.0, 30000.0, 0.01)


    model.nDMaterial('PlateRebar', 3, 2,  0.0)
    model.nDMaterial('PlateRebar', 4, 2, 90.0)
    model.section('LayeredShell', 1,
                7,
                1, cover_1,
                3, rebar,
                4, rebar,
                1, core,
                4, rebar,
                3, rebar,
                1, cover_1)
        

    model.uniaxialMaterial("Concrete01", 6, -6.0, -0.004, -5.0, -0.014)
    model.section('Fiber', 5, '-GJ', 1.0)
    model.patch('rect', 6, 10, 10, -0.5, -0.5, 0.5, 0.5)

    # Geometry--------------------------------------------------------------------------------------------------------------------------
    nx, ny = 10, 10
    points = {
        1: [ 0.0       , 0.0,  0.0],
        2: [-33.282*12 , 0.0, 49.923*12],
        3: [ 0.0       , 0.0, 72.111*12],
        4: [33.282*12  , 0.0, 22.077*12]
    }
   
    surface = model.surface((nx, ny), element='ShellMITC4', args=(1,), points=points)

    # Optional edge frame
    for nodes in surface.walk_edge():
        model.element('PrismFrame', None, nodes, section=5, vertical=[0, 0, 1])


    #------------------------------------------------------------------------------------------------------------------------------
    # Boundary conditions
    model.fixZ( 0.0  , 1,1,1, 1,1,1)
    model.fixZ(72.111*12, 1,1,1, 1,1,1)

    def fix_at(x0, y0, z0, tol):
        fixed = []
        for nid in model.getNodeTags():
            x, y, z = model.nodeCoord(nid)
            if (math.isclose(x, x0, abs_tol=tol) and
                math.isclose(y, y0, abs_tol=tol) and
                math.isclose(z, z0, abs_tol=tol)):
                fixed.append(nid)
        for n in fixed:
            model.fix(n, 1,1,1, 1,1,1)

    fix_at(-33.282*12, 0.0, 49.923*12, tol=1e-1)
    fix_at( 33.282*12, 0.0, 22.077*12, tol=1e-1)
    fix_at(  0.0  , 0.0, 36.0555*12, tol=1)

    return model
#---------------------------------------------------------------------------------------------------------------------------------------
def static_analysis(model, p):
    # Load pattern
    #model.pattern('Plain', 1, 'Linear')
    # 1) Define a linear ramp from 0 → 1
    model.timeSeries('Linear', 1)

    # 2) Create a plain load pattern that uses series tag=1
    model.pattern('Plain', 1, 1)

    ele_tags = model.getEleTags()
    for ele in ele_tags:
        nids = model.eleNodes(ele)
        # Distribute pressure p as nodal force
        for nid in nids:
            model.load(nid, 0.0, -p, 0.0, 0.0, 0.0, 0.0, pattern=1)

    # Define analysis components
    model.integrator('LoadControl', 1.0, 1, 1.0, 10.0)
    model.test("NormDispIncr", 1.0e-2, 30, 2)
    model.algorithm('Newton')
    model.numberer('RCM')
    model.constraints('Plain')
    model.system('SparseGeneral', '-piv')
    model.analysis('Static')
    return model.analyze(1)

##############################################################################################

def main():
    # 1) Write out the node coordinates once
    model0 = create_model()
    coord_fname = 'node_coordinates.csv'
    with open(coord_fname, 'w', newline='') as f_coord:
        writer = csv.writer(f_coord)
        writer.writerow(['Node', 'x', 'y', 'z'])
        for nid in model0.getNodeTags():
            x, y, z = model0.nodeCoord(nid)
            writer.writerow([nid, x, y, z])
    print(f"Wrote {coord_fname} in {os.getcwd()}")

    # 2) Ask which node to track
    target_nid = int(input('Enter node number to track displacement: '))
    linear = False
    if linear:
        history_fname = f'node_{target_nid}_disp_history_linear.csv'
    else:
        history_fname = f'node_{target_nid}_disp_history_nonlinear.csv'

    with open(history_fname, 'w', newline='') as f_hist:
        hist_writer = csv.writer(f_hist)
        hist_writer.writerow(['Iteration', 'p', 'ux', 'uy', 'uz'])

        # 3) Ramp p from 0 up to 5 (inclusive), step dp
        p   = 0.0    # starting pressure
        dp  = 0.45   # pressure increment
        itr = 1
        while p <= 5.0:
            model = create_model()
            try:
                res = static_analysis(model, p)
            except Exception as e:
                print(f"Analysis threw exception at p={p:.3f}: {e}")
                break

            # Non‑zero return → failure to converge
            if res != 0:
                print(f"Analysis failed to converge at iteration {itr}, p = {p:.3f}")
                break

            # 4a) Write full displacements for all nodes
            linear = False 
            if linear:
                disp_fname = f'node_displacements_{itr}_linear.csv'
                with open(disp_fname, 'w', newline='') as f_disp:
                    writer = csv.writer(f_disp)
                    writer.writerow(['Node', 'ux', 'uy', 'uz'])
                    for nid in model.getNodeTags():
                        ux = model.nodeDisp(nid, 1)
                        uy = model.nodeDisp(nid, 2)
                        uz = model.nodeDisp(nid, 3)
                        writer.writerow([nid, ux, uy, uz])
                print(f"Wrote {disp_fname} for iteration {itr} (p = {p:.3f})")

                # 4b) Record just the target node’s displacement
                ux = model.nodeDisp(target_nid, 1)
                uy = model.nodeDisp(target_nid, 2)
                uz = model.nodeDisp(target_nid, 3)
                hist_writer.writerow([itr, round(p, 3), ux, uy, uz])
                print(f"Recorded disp for node {target_nid} at iteration {itr}, p = {p:.3f}")

                # prepare next step
                itr += 1
                p   += dp

            else:
                disp_fname = f'node_displacements_{itr}_nonlinear.csv'
                with open(disp_fname, 'w', newline='') as f_disp:
                    writer = csv.writer(f_disp)
                    writer.writerow(['Node', 'ux', 'uy', 'uz'])
                    for nid in model.getNodeTags():
                        ux = model.nodeDisp(nid, 1)
                        uy = model.nodeDisp(nid, 2)
                        uz = model.nodeDisp(nid, 3)
                        writer.writerow([nid, ux, uy, uz])
                print(f"Wrote {disp_fname} for iteration {itr} (p = {p:.3f})")

                # 4b) Record just the target node’s displacement
                ux = model.nodeDisp(target_nid, 1)
                uy = model.nodeDisp(target_nid, 2)
                uz = model.nodeDisp(target_nid, 3)
                hist_writer.writerow([itr, round(p, 3), ux, uy, uz])
                print(f"Recorded disp for node {target_nid} at iteration {itr}, p = {p:.3f}")

                # prepare next step
                itr += 1
                p   += dp

                
if __name__ == '__main__':
    main()