import cstar_forge

import yaml
from datetime import datetime
from pathlib import Path
import roms_tools as rt

description_outer = "Pacific 1/2 deg (nested)"
description_middle= "Pacific 1/4 deg (nested)"
description_inner = "Pacific 1/8 deg (nested)"

model_name= "cson_roms-marbl_v0.1"

grid_name_outer_down  = "P0p5_down_"
grid_name_middle_down = "P0p25_down_"
grid_name_inner       = "P0p125_"
grid_name_middle_up   = "P0p25_up_"
grid_name_outer_up    = "P0p5_up_"

start_time_outer_down = "2010-01-02"
start_time_middle_down= "2010-01-03"
start_time_inner      = "2010-01-04"
start_time_middle_up  = "2010-01-05"
start_time_outer_up   = "2010-01-06"
end_time              = "2010-01-07" ## note that the end_time variable is the same for all 3 grids


####################################

_macos_dir = Path(__file__).resolve().parent
compile_settings_outer_down_path  = _macos_dir / "compile_outer_down.yml"
compile_settings_middle_down_path = _macos_dir / "compile_middle_down.yml"
compile_settings_inner_path       = _macos_dir / "compile_inner.yml"
compile_settings_middle_up_path   = _macos_dir / "compile_middle_up.yml"
compile_settings_outer_up_path    = _macos_dir / "compile_outer_up.yml"

runtime_settings_outer_path  = _macos_dir / "runtime_outer.yml"
runtime_settings_middle_path = _macos_dir / "runtime_middle.yml"
runtime_settings_inner_path  = _macos_dir / "runtime_inner.yml"


with compile_settings_outer_down_path.open("r", encoding="utf-8") as f:
    compile_settings_outer_down = yaml.safe_load(f) or {}

with compile_settings_middle_down_path.open("r", encoding="utf-8") as f:
    compile_settings_middle_down = yaml.safe_load(f) or {}

with compile_settings_inner_path.open("r", encoding="utf-8") as f:
    compile_settings_inner = yaml.safe_load(f) or {}

with compile_settings_middle_up_path.open("r", encoding="utf-8") as f:
    compile_settings_middle_up = yaml.safe_load(f) or {}

with compile_settings_outer_up_path.open("r", encoding="utf-8") as f:
    compile_settings_outer_up = yaml.safe_load(f) or {}


with runtime_settings_outer_path.open("r", encoding="utf-8") as f:
    runtime_settings_outer = yaml.safe_load(f) or {}

with runtime_settings_middle_path.open("r", encoding="utf-8") as f:
    runtime_settings_middle = yaml.safe_load(f) or {}

with runtime_settings_inner_path.open("r", encoding="utf-8") as f:
    runtime_settings_inner = yaml.safe_load(f) or {}


###################################


grid_kwargs_outer = dict[str, float](
    nx=40,
    ny=40,
    size_x=100,   # km (longitude direction at ~49N)
    size_y=200,   # km (latitude direction)
    center_lon=-139.5,
    center_lat=53,
    rot=0,
    N=10,  # number of vertical levels
    theta_s=6.0,  # surface control parameter
    theta_b=3.0,  # bottom control parameter
    hc=250.0,  # critical depth
)

grid_kwargs_middle = dict[str, float](
    nx=40,
    ny=40,
    size_x=50,   # km (longitude direction at ~49N)
    size_y=100,   # km (latitude direction)
    center_lon=-139.5,
    center_lat=53,
    rot=0,
    N=10,  # number of vertical levels
    theta_s=6.0,  # surface control parameter
    theta_b=3.0,  # bottom control parameter
    hc=250.0,  # critical depth
)

grid_kwargs_inner = dict[str, float](
    nx=40,
    ny=40,
    size_x=25,   # km (longitude direction at ~49N)
    size_y=50,   # km (latitude direction)
    center_lon=-139.5,
    center_lat=53,
    rot=0,
    N=10,  # number of vertical levels
    theta_s=6.0,  # surface control parameter
    theta_b=3.0,  # bottom control parameter
    hc=250.0,  # critical depth
)


#########################################


times = [datetime(2010, 1, 4, 1),
           datetime(2010, 1, 4, 10),
           datetime(2010, 1, 4, 23),
          ]

volume_fluxes = [0, 100, 500] # m3/s
tracer_fluxes1 = {"ALK": [0.0, 30.0*10**6, 0.0]} # meq/s
tracer_fluxes2 = {"ALK": [0.0, 3.0*10**6, 0.0]} # meq/s
tracer_concentrations = {
    "ALK": [1900.0, 2100.0, 1900.0],  # meq/m3
    "temp": 20.0,  # degrees C
    "salt": 1.0,  # psu
}

cdr_tracer_release1 = rt.TracerPerturbation(
    name="release_river1",
    lat=53,  # degree N
    lon=-139.5,  # degree E
    depth=10,  # m
    hsc=500,
    vsc=300,
    times=times,
    tracer_fluxes=tracer_fluxes1,
)

cdr_tracer_release2 = rt.TracerPerturbation(
    name="release_river2",
    lat=53,  # degree N
    lon=-139.5,  # degree E
    depth=10,  # m
    hsc=500,
    vsc=300,
    times=times,
    tracer_fluxes=tracer_fluxes2,
)

# CDR_forcing must be a dict of kwargs for roms_tools.CDRForcing (not a list of releases).
# At minimum: start_time, end_time, releases (list of TracerPerturbation or a ReleaseCollector).
_sim_start = datetime.strptime(start_time_inner, "%Y-%m-%d")
_sim_end = datetime.strptime(end_time, "%Y-%m-%d")
cdr_forcing_cfg = {
    "start_time": _sim_start,
    "end_time": _sim_end,
    # All CDR releases for this run go in one list (unique `name` per release).
    "releases": [cdr_tracer_release1, cdr_tracer_release2],
}

######################################


boundaries_outer= dict(
    south= True,
    east= True,
    north= True,
    west= True,
)

boundaries_middle= dict(
    south= True,
    east= True,
    north= True,
    west= True,
)

boundaries_inner= dict(
    south= True,
    east= True,
    north= True,
    west= True,
)


#######################################


partitioning_outer= dict(
    n_procs_x= 2,
    n_procs_y= 4
)

partitioning_middle= dict(
    n_procs_x= 4,
    n_procs_y= 2
)

partitioning_inner= dict(
    n_procs_x= 4,
    n_procs_y= 4
)


######################################

ocn_outer_down = cstar_forge.CstarSpecBuilder(
    description=description_outer,
    model_name=model_name,
    grid_name=grid_name_outer_down,
    grid_kwargs=grid_kwargs_outer,
    grid_kwargs_child=grid_kwargs_middle,
    open_boundaries=boundaries_outer,
    start_time=start_time_outer_down,
    end_time=end_time,
    partitioning=partitioning_outer,
)

ocn_middle_down = cstar_forge.CstarSpecBuilder(
    description=description_middle,
    model_name=model_name,
    grid_name=grid_name_middle_down,
    grid_kwargs=grid_kwargs_middle,
    grid_kwargs_parent=grid_kwargs_outer,
    grid_kwargs_child=grid_kwargs_inner,
    open_boundaries=boundaries_middle,
    start_time=start_time_middle_down,
    end_time=end_time,
    partitioning=partitioning_middle,
)

ocn_inner = cstar_forge.CstarSpecBuilder(
    description=description_inner,
    model_name=model_name,
    grid_name=grid_name_inner,
    grid_kwargs=grid_kwargs_inner,
    grid_kwargs_parent=grid_kwargs_middle,
    open_boundaries=boundaries_inner,
    start_time=start_time_inner,
    end_time=end_time,
    partitioning=partitioning_inner,
    CDR_forcing=cdr_forcing_cfg,
)

ocn_middle_up = cstar_forge.CstarSpecBuilder(
    description=description_middle,
    model_name=model_name,
    grid_name=grid_name_middle_up,
    grid_kwargs=grid_kwargs_middle,
    grid_kwargs_parent=grid_kwargs_outer,
    grid_kwargs_child=grid_kwargs_inner,
    open_boundaries=boundaries_middle,
    start_time=start_time_middle_up,
    end_time=end_time,
    partitioning=partitioning_middle,
)

ocn_outer_up = cstar_forge.CstarSpecBuilder(
    description=description_outer,
    model_name=model_name,
    grid_name=grid_name_outer_up,
    grid_kwargs=grid_kwargs_outer,
    open_boundaries=boundaries_outer,
    start_time=start_time_outer_up,
    end_time=end_time,
    partitioning=partitioning_outer,
)


#####################################

sim = [ocn_outer_down, ocn_middle_down, ocn_inner, ocn_middle_up, ocn_outer_up]
compile = [compile_settings_outer_down, compile_settings_middle_down, compile_settings_inner,
           compile_settings_middle_up, compile_settings_outer_up]
runtime = [runtime_settings_outer, runtime_settings_middle, runtime_settings_inner,
           runtime_settings_middle, runtime_settings_outer]

for ocn,ct,rt in zip(sim,compile,runtime):
    # ensure that source data is staged locally
    ocn.ensure_source_data()

    # prepare model input
    ocn.generate_inputs(clobber=False) # setting clobber=True will overwrite existing files

    # configure and build the model
    ocn.configure_build(
        compile_time_settings=ct,
        run_time_settings=rt,
    )

    ocn.prep_cstar_environment(
        account_key = None,  # None gets from machine config or override here
        queue_name = None,  # None gets from machine config or override here
        walltime = "00:10:00",
        clobber = True,  # recommend True, but it will clear previous results from this run
        n_procs_available = 0,  # 0 is auto-detect, change if on a login or shared node to not overuse resources
    )

#    handler = ocn.run()
#    print(handler)



