# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""QQ3DRenderer."""

from typing import List, Union

import pandas as pd
from collections import defaultdict

import pyEPR as epr
from pyEPR.ansys import ureg
from pyEPR.reports import _plot_q3d_convergence_main, _plot_q3d_convergence_chi_f
from pyEPR.calcs.convert import Convert
from qiskit_metal import Dict
from qiskit_metal.renderers.renderer_ansys.ansys_renderer import QAnsysRenderer
from qiskit_metal.toolbox_metal.parsing import is_true

from .. import config
if not config.is_building_docs():
    from qiskit_metal.analyses.quantization.lumped_capacitive import extract_transmon_coupled_Noscillator


class QQ3DRenderer(QAnsysRenderer):
    """Subclass of QAnsysRenderer for running Q3D simulations.

    QAnsysRenderer Default Options:
        * Lj: '10nH' -- Lj has units of nanoHenries (nH)
        * Cj: 0 -- Cj *must* be 0 for pyEPR analysis! Cj has units of femtofarads (fF)
        * _Rj: 0 -- _Rj *must* be 0 for pyEPR analysis! _Rj has units of Ohms
        * max_mesh_length_jj: '7um' -- Maximum mesh length for Josephson junction elements
        * project_path: None -- Default project path; if None --> get active
        * project_name: None -- Default project name
        * design_name: None -- Default design name
        * ansys_file_extension: '.aedt' -- Ansys file extension for 2016 version and newer
        * x_buffer_width_mm: 0.2 -- Buffer between max/min x and edge of ground plane, in mm
        * y_buffer_width_mm: 0.2 -- Buffer between max/min y and edge of ground plane, in mm
    """

    name = 'q3d'
    """name"""

    q3d_options = Dict(material_type='pec',
                       material_thickness='200nm',
                       add_setup=Dict(freq_ghz='5.0',
                                      name='Setup',
                                      save_fields='False',
                                      enabled='True',
                                      max_passes='15',
                                      min_passes='2',
                                      min_converged_passes='2',
                                      percent_error='0.5',
                                      percent_refinement='30',
                                      auto_increase_solution_order='True',
                                      solution_order='High',
                                      solver_type='Iterative'),
                       get_capacitance_matrix=Dict(variation='',
                                                   solution_kind='AdaptivePass',
                                                   pass_number='3'))
    """Q3d options"""

    def __init__(self,
                 design: 'QDesign',
                 initiate=True,
                 render_template: Dict = None,
                 render_options: Dict = None):
        """Create a QRenderer for Q3D simulations, subclassed from
        QAnsysRenderer.

        Args:
            design (QDesign): Use QGeometry within QDesign to obtain elements for Ansys.
            initiate (bool, optional): True to initiate the renderer. Defaults to True.
            render_template (Dict, optional): Typically used by GUI for template options for GDS. Defaults to None.
            render_options (Dict, optional): Used to override all options. Defaults to None.
        """
        super().__init__(design=design,
                         initiate=initiate,
                         render_template=render_template,
                         render_options=render_options)
        QQ3DRenderer.load()

    @property
    def boundaries(self):
        """Reference to BoundarySetup in active design in Ansys.

        Returns:
            win32com.client.CDispatch: COMObject GetModule, obtained by running within pyEPR: design.GetModule("BoundarySetup")
        """
        if self.pinfo:
            if self.pinfo.design:
                return self.pinfo.design._boundaries

    @property
    def setup_options(self):
        """Setup the q3d options."""
        return self.q3d_options['add_setup']

    def render_design(self,
                      selection: Union[list, None] = None,
                      open_pins: Union[list, None] = None,
                      box_plus_buffer: bool = True):
        """Initiate rendering of components in design contained in selection,
        assuming they're valid. Components are rendered before the chips they
        reside on, and subtraction of negative shapes is performed at the very
        end.

        First obtain a list of IDs of components to render and a corresponding case, denoted by self.qcomp_ids
        and self.case, respectively. If self.case == 1, all components in QDesign are to be rendered.
        If self.case == 0, a strict subset of components in QDesign are to be rendered. Otherwise, if
        self.case == 2, one or more component names in selection cannot be found in QDesign.

        Chip_subtract_dict consists of component names (keys) and a set of all elements within each component that
        will eventually be subtracted from the ground plane. Add objects that are perfect conductors and/or have
        meshing to self.assign_perfE and self.assign_mesh, respectively; both are initialized as empty lists. Note
        that these objects are "refreshed" each time render_design is called (as opposed to in the init function)
        to clear QAnsysRenderer of any leftover items from the last call to render_design.

        Among the components selected for export, there may or may not be unused (unconnected) pins.
        The second parameter, open_pins, contains tuples of the form (component_name, pin_name) that
        specify exactly which pins should be open rather than shorted during the simulation. Both the
        component and pin name must be specified because the latter could be shared by multiple
        components. All pins in this list are rendered with an additional endcap in the form of a
        rectangular cutout, to be subtracted from its respective plane.

        The final parameter, box_plus_buffer, determines how the chip is drawn. When set to True, it takes the
        minimum rectangular bounding box of all rendered components and adds a buffer of x_buffer_width_mm and
        y_buffer_width_mm horizontally and vertically, respectively, to the chip size. The center of the chip
        lies at the midpoint x/y coordinates of the minimum rectangular bounding box and may change depending
        on which components are rendered and how they're positioned. If box_plus_buffer is False, however, the
        chip position and dimensions are taken from the chip info dictionary found in self.design, irrespective
        of what's being rendered. While this latter option is faster because it doesn't require calculating a
        bounding box, it runs the risk of rendered components being too close to the edge of the chip or even
        falling outside its boundaries.

        Args:
            selection (Union[list, None], optional): List of components to render. Defaults to None.
            open_pins (Union[list, None], optional): List of tuples of pins that are open. Defaults to None.
            box_plus_buffer (bool): Either calculate a bounding box based on the location of rendered geometries
                                     or use chip size from design class.
        """
        self.qcomp_ids, self.case = self.get_unique_component_ids(selection)

        if self.case == 2:
            self.logger.warning(
                'Unable to proceed with rendering. Please check selection.')
            return

        self.chip_subtract_dict = defaultdict(set)
        self.assign_perfE = []
        self.assign_mesh = []

        self.render_tables()
        self.add_endcaps(open_pins)

        self.render_chips(draw_sample_holder=False,
                          box_plus_buffer=box_plus_buffer)
        self.subtract_from_ground()
        self.add_mesh()

        self.assign_thin_conductor()
        self.assign_nets()

    def render_tables(self):
        """
        Render components in design grouped by table type (path or poly, but not junction).
        """
        for table_type in self.design.qgeometry.get_element_types():
            if table_type != 'junction':
                self.render_components(table_type)

    def assign_thin_conductor(self,
                              material_type: str = 'pec',
                              thickness: str = '200 nm',
                              name: str = None):
        """Assign thin conductor property to all exported shapes. Unless
        otherwise specified, all 2-D shapes are pec's with a thickness of 200
        nm.

        Args:
            material_type (str): Material assignment.
            thickness (str): Thickness of thin conductor. Must include units.
            name (str): Name assigned to this group of thin conductors.
        """
        self.boundaries.AssignThinConductor([
            "NAME:" + (name if name else "ThinCond1"), "Objects:=",
            self.assign_perfE, "Material:=", material_type if material_type else
            self.q3d_options['material_type'], "Thickness:=",
            thickness if thickness else self.q3d_options['material_thickness']
        ])

    def assign_nets(self):
        """Auto assign nets to exported shapes."""
        self.boundaries.AutoIdentifyNets()

    def activate_q3d_setup(self, setup_name_activate: str = None):
        """For active design, either get existing setup, make new setup with
        name, or make new setup with default name.

        Args:
            setup_name_activate (str, optional): If name exists for setup, then have pinfo
              reference it.  If name for setup does not exist, create a new setup with the name.
              If name is None, create a new setup with default name.
        """
        if self.pinfo:
            if self.pinfo.project:
                if self.pinfo.design:
                    # look for setup name, if not there, then add a new one
                    if setup_name_activate:
                        all_setup_names = self.pinfo.design.get_setup_names()
                        self.pinfo.setup_name = setup_name_activate
                        if setup_name_activate in all_setup_names:
                            # When name is given and in design. So have pinfo reference existing setup.
                            self.pinfo.setup = self.pinfo.get_setup(
                                self.pinfo.setup_name)
                        else:
                            # When name is given, but not in design. So make a new setup with given name.
                            self.pinfo.setup = self.add_q3d_setup(
                                name=self.pinfo.setup_name)
                    else:
                        # When name is not given, so use default name for setup.
                        # default name is "Setup"
                        self.pinfo.setup = self.add_q3d_setup()
                        self.pinfo.setup_name = self.pinfo.setup.name
                else:
                    self.logger.warning(
                        " The design within a project is not available, have you opened a design?"
                    )
            else:
                self.logger.warning(
                    "Project not available, have you opened a project?")
        else:
            self.logger.warning(
                "Have you run connect_ansys()?  Cannot find a reference to Ansys in QRenderer."
            )

    def add_q3d_setup(self,
                      freq_ghz: float = None,
                      name: str = None,
                      save_fields: bool = None,
                      enabled: bool = None,
                      max_passes: int = None,
                      min_passes: int = None,
                      min_converged_passes: int = None,
                      percent_error: float = None,
                      percent_refinement: int = None,
                      auto_increase_solution_order: bool = None,
                      solution_order: str = None,
                      solver_type: str = None):
        """Create a solution setup in Ansys Q3D. If user does not provide
        arguments, they will be obtained from q3d_options dict.

        Args:
            freq_ghz (float, optional): Frequency in GHz. Defaults to 5..
            name (str, optional): Name of solution setup. Defaults to "Setup".
            save_fields (bool, optional): Whether or not to save fields. Defaults to False.
            enabled (bool, optional): Whether or not setup is enabled. Defaults to True.
            max_passes (int, optional): Maximum number of passes. Defaults to 15.
            min_passes (int, optional): Minimum number of passes. Defaults to 2.
            min_converged_passes (int, optional): Minimum number of converged passes. Defaults to 2.
            percent_error (float, optional): Error tolerance as a percentage. Defaults to 0.5.
            percent_refinement (int, optional): Refinement as a percentage. Defaults to 30.
            auto_increase_solution_order (bool, optional): Whether or not to increase solution order automatically. Defaults to True.
            solution_order (str, optional): Solution order. Defaults to 'High'.
            solver_type (str, optional): Solver type. Defaults to 'Iterative'.
        """
        su = self.setup_options

        if not freq_ghz:
            freq_ghz = float(self.parse_value(su['freq_ghz']))
        if not name:
            name = self.parse_value(su['name'])
        if not save_fields:
            save_fields = is_true(su['save_fields'])
        if not enabled:
            enabled = is_true(su['enabled'])
        if not max_passes:
            max_passes = int(self.parse_value(su['max_passes']))
        if not min_passes:
            min_passes = int(self.parse_value(su['min_passes']))
        if not min_converged_passes:
            min_converged_passes = int(
                self.parse_value(su['min_converged_passes']))
        if not percent_error:
            percent_error = float(self.parse_value(su['percent_error']))
        if not percent_refinement:
            percent_refinement = int(self.parse_value(su['percent_refinement']))
        if not auto_increase_solution_order:
            auto_increase_solution_order = is_true(
                su['auto_increase_solution_order'])
        if not solution_order:
            solution_order = self.parse_value(su['solution_order'])
        if not solver_type:
            solver_type = self.parse_value(su['solver_type'])

        if self.pinfo:
            if self.pinfo.design:
                return self.pinfo.design.create_q3d_setup(
                    freq_ghz=freq_ghz,
                    name=name,
                    save_fields=save_fields,
                    enabled=enabled,
                    max_passes=max_passes,
                    min_passes=min_passes,
                    min_converged_passes=min_converged_passes,
                    percent_error=percent_error,
                    percent_refinement=percent_refinement,
                    auto_increase_solution_order=auto_increase_solution_order,
                    solution_order=solution_order,
                    solver_type=solver_type)

    def edit_q3d_setup(self, setup_args: Dict):
        """User can pass key/values to edit the setup for active q3d setup.

        Args:
            setup_args (Dict): a Dict with possible keys/values.

        **setup_args** dict contents:
            * freq_ghz (float, optional): Frequency in GHz. Defaults to 5..
            * name (str, optional): Name of solution setup. Defaults to "Setup".
            * max_passes (int, optional): Maximum number of passes. Defaults to 15.
            * min_passes (int, optional): Minimum number of passes. Defaults to 2.
            * percent_error (float, optional): Error tolerance as a percentage. Defaults to 0.5.

            Note, that these 7 arguments are currently NOT implemented:
            Ansys API named EditSetup requires all arguments to be passed, but
            presently have no way to read all of the setup.
            Also, self.pinfo.setup does not have all the @property variables
            used for Setup.
            * save_fields (bool, optional): Whether or not to save fields. Defaults to False.
            * enabled (bool, optional): Whether or not setup is enabled. Defaults to True.
            * min_converged_passes (int, optional): Minimum number of converged passes. Defaults to 2.
            * percent_refinement (int, optional): Refinement as a percentage. Defaults to 30.
            * auto_increase_solution_order (bool, optional): Whether or not to increase solution order automatically. Defaults to True.
            * solution_order (str, optional): Solution order. Defaults to 'High'.
            * solver_type (str, optional): Solver type. Defaults to 'Iterative'.
        """

        if self.pinfo:
            if self.pinfo.project:
                if self.pinfo.design:
                    if self.pinfo.design.solution_type == 'Q3D':
                        if self.pinfo.setup_name != setup_args.name:
                            self.design.logger.warning(
                                f'The name of active setup={self.pinfo.setup_name} does not match'
                                f'the name of of setup_args.name={setup_args.name}. '
                                f'To use this method, activate the desired Setup before editing it. '
                                f'The setup_args was not used to update the active Setup.'
                            )
                            return

                        for key, value in setup_args.items():
                            if key == "name":
                                continue  #Checked for above.
                            if key == "freq_ghz":
                                if not isinstance(value, float):
                                    self.logger.warning(
                                        'The value for min_freq_ghz should be a '
                                        f'float.  The present value is {value}.'
                                    )
                                else:
                                    ### This EditSetup works if we change all of the arguments
                                    # at the same time.  We don't always want to change all of them.
                                    # Need to have a way to read all of the arguments to
                                    # avoid overwriting arguments. Presently, will use
                                    # the variables set in pyEPR with @property.
                                    # args_editsetup = [
                                    #     f"NAME:{setup_args.name}",
                                    #     "AdaptiveFreq:=", f"{value}GHz",
                                    #     "SaveFields:=", False, "Enabled:=",
                                    #     True,
                                    #     [
                                    #         "NAME:Cap", "MaxPass:=", 15,
                                    #         "MinPass:=", 2, "MinConvPass:=", 2,
                                    #         "PerError:=", 0.5, "PerRefine:=",
                                    #         30, "AutoIncreaseSolutionOrder:=",
                                    #         True, "SolutionOrder:=", "High",
                                    #         "Solver Type:=", "Iterative"
                                    #     ]
                                    # ]
                                    # self.pinfo.design._setup_module.EditSetup(
                                    #     setup_args.name, args_editsetup)
                                    self.pinfo.setup.frequency = f"{value}GHz"
                                    continue
                            if key == 'max_passes':
                                if not isinstance(value, int):
                                    self.logger.warning(
                                        'The value for max_passes should be an int. '
                                        f'The present value is {value}.')
                                else:
                                    self.pinfo.setup.max_pass = value
                                    continue

                            if key == 'min_passes':
                                if not isinstance(value, int):
                                    self.logger.warning(
                                        'The value for min_passes should be an int. '
                                        f'The present value is {value}.')
                                else:
                                    self.pinfo.setup.min_pass = value
                                    continue

                            if key == 'percent_error':
                                if not isinstance(value, float):
                                    self.logger.warning(
                                        'The value for percent_error should be a float. '
                                        f'The present value is {value}.')
                                else:
                                    self.pinfo.setup.pct_error = value
                                    continue

                            self.design.logger.warning(
                                f'In setup_args, key={key}, value={value} is not in pinfo.setup, '
                                'the key/value pair from setup_args not added to Setup in Ansys.'
                            )

                    else:
                        self.logger.warning(
                            'The design does not have solution type as "Q3D". The Setup not updated.'
                        )
                else:
                    self.logger.warning(
                        'A design is not in active project. The Setup not updated.'
                    )
            else:
                self.logger.warning(
                    "Project not available, have you opened a project? Setup not updated."
                )
        else:
            self.logger.warning(
                "Have you run connect_ansys()?  "
                "Cannot find a reference to Ansys in QRenderer. Setup not updated. "
            )

    def analyze_setup(self, setup_name: str):
        """Run a specific solution setup in Ansys Q3D.

        Args:
            setup_name (str): Name of setup.
        """
        if self.pinfo:
            setup = self.pinfo.get_setup(setup_name)
            setup.analyze()

    def get_capacitance_matrix(self,
                               variation: str = '',
                               solution_kind: str = 'LastAdaptive',
                               pass_number: int = 3):
        """Obtain capacitance matrix in a dataframe format. Must be executed
        *after* analyze_setup.

        Args:
            variation (str, optional): An empty string returns nominal variation. Otherwise need the list. Defaults to ''
            solution_kind (str, optional): Solution type. Defaults to 'LastAdaptive'.
                Set to 'AdaptivePass' to return the capacitance matrix of a specific pass.
            pass_number (int, optional): Which adaptive pass to acquire the capacitance
                matrix from. Defaults to 3, only in effect with 'AdaptivePass' chosen.
        """
        qo = self.q3d_options['get_capacitance_matrix']

        if not variation:
            variation = self.parse_value(qo['variation'])
        if not solution_kind:
            solution_kind = self.parse_value(qo['solution_kind'])
        if not pass_number:
            pass_number = int(self.parse_value(qo['pass_number']))

        if self.pinfo:
            df_cmat, user_units, _, _ = self.pinfo.setup.get_matrix(
                variation=variation,
                solution_kind=solution_kind,
                pass_number=pass_number)
            return df_cmat

    def lumped_oscillator_vs_passes(self,
                                    Lj_nH: float,
                                    Cj_fF: float,
                                    N: int,
                                    fr: Union[list, float],
                                    fb: Union[list, float],
                                    maxPass: int,
                                    variation: str = '',
                                    g_scale: float = 1) -> dict:
        """Obtain dictionary composed of pass numbers (keys) and their
        respective capacitance matrices (values). All capacitance matrices
        utilize the same values for Lj_nH and onwards in the list of arguments.

        Args:
            Lj_nH (float): Junction inductance (in nH)
            Cj_fF (float): Junction capacitance (in fF)
            N (int): Coupling pads (1 readout, N - 1 bus)
            fr (Union[list, float]):Readout frequencies (in GHz). fr can be a list with the order
                they appear in the capMatrix.
            fb (Union[list, float]): Coupling bus frequencies (in GHz). fb can be a list with the order
                they appear in the capMatrix.
            maxPass (int): Maximum number of passes
            variation (str, optional): An empty string returns nominal variation. Otherwise need the list. Defaults to ''.
            g_scale (float, optional): Scale factor. Defaults to 1..

        Returns:
            dict: A dictionary composed of pass numbers (keys) and their respective capacitance matrices (values)
        """
        IC_Amps = Convert.Ic_from_Lj(Lj_nH, 'nH', 'A')
        CJ = ureg(f'{Cj_fF} fF').to('farad').magnitude
        fr = ureg(f'{fr} GHz').to('GHz').magnitude
        fb = [ureg(f'{freq} GHz').to('GHz').magnitude for freq in fb]
        RES = {}
        for i in range(1, maxPass):
            df_cmat, user_units, _, _ = self.pinfo.setup.get_matrix(
                variation=variation,
                solution_kind='AdaptivePass',
                pass_number=i)
            c_units = ureg(user_units).to('farads').magnitude
            res = extract_transmon_coupled_Noscillator(
                df_cmat.values * c_units,
                IC_Amps,
                CJ,
                N,
                fb,
                fr,
                g_scale=1,
                print_info=bool(i == maxPass - 1))
            RES[i] = res
        RES = pd.DataFrame(RES).transpose()
        RES['χr MHz'] = abs(RES['chi_in_MHz'].apply(lambda x: x[0]))
        RES['gr MHz'] = abs(RES['gbus'].apply(lambda x: x[0]))
        return RES

    def plot_convergence_main(self, RES: pd.DataFrame):
        """Plot alpha and frequency versus pass number, as well as convergence
        of delta (in %).

        Args:
            RES (pd.DataFrame): Dictionary of capacitance matrices versus pass number, organized as pandas table.
        """
        if self._pinfo:
            eprd = epr.DistributedAnalysis(self._pinfo)
            epr.toolbox.plotting.mpl_dpi(110)
            return _plot_q3d_convergence_main(eprd, RES)

    def plot_convergence_chi(self, RES: pd.DataFrame):
        """Plot convergence of chi and g, both in MHz, as a function of pass
        number.

        Args:
            RES (pd.DataFrame): Dictionary of capacitance matrices versus pass number, organized as pandas table.
        """
        epr.toolbox.plotting.mpl_dpi(110)
        return _plot_q3d_convergence_chi_f(RES)

    def add_q3d_design(self, name: str, connect: bool = True):
        """Add a q3d design with the given name to the project.

        Args:
            name (str): Name of the new q3d design
            connect (bool, optional): Should we connect this session to this design? Defaults to True.
        """
        if self.pinfo:
            try:
                adesign = self.pinfo.project.new_q3d_design(name)
            except AttributeError:
                self.logger.error(
                    'Please install a more recent version of pyEPR (>=0.8.4.4)')
            if connect:
                self.connect_ansys_design(adesign.name)
            return adesign
        else:
            self.logger.info("Are you mad?? You have to connect to ansys and a project " \
                            "first before creating a new design . Use self.connect_ansys()")

    def activate_q3d_design(self, name: str = "MetalQ3ds"):
        """Add a q3d design with the given name to the project.  If the design
        exists, that will be added WITHOUT altering the suffix of the design
        name.

        Args:
            name (str): Name of the new q3d design
        """

        if self.pinfo:
            if self.pinfo.project:
                try:
                    names_in_design = self.pinfo.project.get_design_names()
                except AttributeError:
                    self.logger.error(
                        'Please install a more recent version of pyEPR (>=0.8.4.5)'
                    )

                if name in names_in_design:
                    self.pinfo.connect_design(name)
                    oDesktop = self.pinfo.design.parent.parent._desktop  # self.pinfo.design does not work
                    oProject = oDesktop.SetActiveProject(
                        self.pinfo.project_name)
                    oDesign = oProject.SetActiveDesign(name)
                else:
                    self.logger.warning(
                        f'The name={name} was not in active project.  '
                        'A new design will be inserted to the project.  '
                        f'Names in active project are: \n{names_in_design}.  ')
                    adesign = self.add_q3d_design(name=name, connect=True)

            else:
                self.logger.warning(
                    "Project not available, have you opened a project?")
        else:
            self.logger.warning(
                "Have you run connect_ansys()?  Cannot find a reference to Ansys in QRenderer."
            )
