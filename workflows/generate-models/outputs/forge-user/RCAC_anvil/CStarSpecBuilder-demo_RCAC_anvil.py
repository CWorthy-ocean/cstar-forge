"""Create a new domain and run a ROMS simulation using C-STAR Forge."""

import asyncio
import cstar_forge
from datetime import datetime
from glob import glob

import matplotlib.pyplot as plt
import xarray as xr

####################################
# Environment and Machine Information
####################################

env = cstar_forge.config.get_environment_info()

print("Machine Information")
print(f"  Hostname: {env.hostname}")
print(f"  System Tag: {env.system_tag}")
print(f"  OS: {env.os_info}")
print()
print("Environment Summary")
print(f"  Python Version: {env.python_version}")
print(f"  Python Executable: {env.python_executable}")
print(f"  Conda/Micromamba Environment: {env.env_info}")
print(f"  Kernel: {env.kernel_spec}")
print(f"Execution timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

####################################
# Domain configuration
####################################

grid_name = "test-tiny"
model_name = "cson_roms-marbl_v0.1"
start_time = datetime(2012, 1, 1)
end_time = datetime(2012, 1, 2)

grid_kwargs = dict[str, float](
    nx=6,
    ny=2,
    size_x=500,
    size_y=1000,
    center_lon=0,
    center_lat=55,
    rot=10,
    N=3,  # number of vertical levels
    theta_s=5.0,  # surface control parameter
    theta_b=2.0,  # bottom control parameter
    hc=250.0,  # critical depth
)

boundaries = {
    "south": False,
    "east": True,
    "north": True,
    "west": False,
}

partitioning = {
    "n_procs_x": 1,  # number of partitions in xi (x)
    "n_procs_y": 1,  # number of partitions in eta (y)
}

####################################
# Initialize CstarSpecBuilder
####################################

ocn = cstar_forge.CstarSpecBuilder(
    description="Test tiny",
    model_name=model_name,
    grid_name=grid_name,
    grid_kwargs=grid_kwargs,
    open_boundaries=boundaries,
    start_time=start_time,
    end_time=end_time,
    partitioning=partitioning,
)

####################################
# Visualize the grid
####################################

ocn.grid.plot()

####################################
# Prepare source data
####################################

ocn.ensure_source_data()

####################################
# Generate input files
####################################

ocn.generate_inputs(clobber=False)  # setting clobber=True will overwrite existing files

####################################
# Access generated input datasets
####################################

for key in ocn.datasets.keys():
    print("-" * 100)
    print(key)
    print(ocn.datasets[key])

####################################
# Configure build
####################################

ocn.configure_build(compile_time_settings={}, run_time_settings={})

####################################
# Pre-run setup
####################################

ocn.prep_cstar_environment(
    account_key=None,  # None gets from machine config or override here
    queue_name=None,  # None gets from machine config or override here
    walltime="00:10:00",
    clobber=True,  # recommend True, but it will clear previous results from this run
    n_procs_available=1,  # 0 is auto-detect, change if on a login or shared node to not overuse resources
)

####################################
# Run model simulation
####################################

asyncio.run(ocn.run())

####################################
# Visualize model output
####################################

#bgc_glob = str(
#    ocn.run_output_dir / "output" / "joined_output" / (ocn.casename + "_bgc.*")
#)
#print(bgc_glob)
#
#files = glob(str(ocn.run_output_dir / "output" / "joined_output" / "output_bgc.*"))
#ds = xr.open_mfdataset(files)
#ds = ds.where(ocn.grid.ds.mask_rho)
#ds.DIC.isel(time=0, s_rho=-1).plot()
#plt.show()

####################################
# Set blueprint state
####################################

#ocn.set_blueprint_state(state="draft")
