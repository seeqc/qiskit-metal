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

from typing import List, Tuple, Union, Any, Iterable, Dict
from qiskit_metal.renderers.renderer_ansys.hfss_renderer import QHFSSRenderer, QAnsysRenderer
from qiskit_metal.renderers.renderer_ansys.q3d_renderer import QQ3DRenderer


class Sweeping():
    """The methods allow users to sweep a variable in a components's options.
    Need access to renderers which are registered in QDesign."""

    def __init__(self, design: 'QDesign'):
        """Give QDesign to this class so Sweeping can access the registered
        QRenderers.

        Args:
            design (QDesign): Used to access the QRenderers.
        """
        self.design = design

    def option_value(self, a_dict, search: str) -> str:
        """Get value from dict based on key.  This method is used for unknown
        depth, dict search, within a dict.

        Args:
            a_dict (dict): Dictionary to get values from
            search (str): String to search for

        Returns:
            str: Value from the dictionary of the searched term.
        """
        value = a_dict[search]
        return value

    def error_check_sweep_input(self, qcomp_name: str, option_name: str,
                                option_sweep: list) -> Tuple[list, Dict, int]:
        """ Implement error checking of data for sweeping.

        Args:
            qcomp_name (str): Component that contains the option to be swept.
            option_name (str): The option within qcomp_name to sweep.
            option_sweep (list): Each entry in the list is a value 
                                for option_name.

        Returns:
            list: Traverse the option Dict.  
            addict.addict.Dict: Value from the dictionary of the searched key.
            int: Observation of searching for data from arguments.

            * 0 Error not detected in the input-data.
            * 1 qcomp_name not registered in design.
            * 2 option_name is empty.
            * 3 option_name is not found as key in dict.
            * 4 option_sweep is empty, need at least one entry.
        """
        option_path = None
        a_value = None

        if len(option_sweep) == 0:
            return option_path, a_value, 4

        if option_name:
            option_path = option_name.split('.')
        else:
            return option_path, a_value, 2

        if qcomp_name in self.design.components.keys():
            qcomp_options = self.design.components[qcomp_name].options
        else:
            return option_path, a_value, 1

        a_value = qcomp_options

        # All but the last item in list.
        for name in option_path[:-1]:
            if name in a_value:
                a_value = self.option_value(a_value, name)
            else:
                self.design.logger.warning(f'Key="{name}" is not in dict.')
                return option_path, a_value, 3

        return option_path, a_value, 0

    def prep_eigenmode_setup(self, setup_args: Dict) -> int:
        """User can pass arguments for method eigenmode setup.  If not passed, 
        method will use the options in HFSS default_options. The name of setup 
        will be "Sweep_em_setup".  If a setup named "Sweep_em_setup" exists 
        in the project, it will be deleted, and a new setup will be added 
        with the arguments from setup_args. 

        Assume: Error checking has already occurred for existence of Ansys, 
        project, and HFSS eigenmode design has been connected to pinfo.

        Args:
            setup_args (Dict):  Maximum  keys used in setup_args.

        **setup_args** dict contents:
            * min_freq_ghz (int, optional): Minimum frequency in GHz. 
              Defaults to 1.
            * n_modes (int, optional): Number of modes. Defaults to 1.
            * max_delta_f (float, optional): Maximum difference in 
              freq between consecutive passes. 
              Defaults to 0.5.
            * max_passes (int, optional): Maximum number of passes. 
              Defaults to 10.
            * min_passes (int, optional): Minimum number of passes. 
              Defaults to 1.
            * min_converged (int, optional): Minimum number of converged 
              passes.  Defaults to 1.
            * pct_refinement (int, optional): Percent refinement. 
              Defaults to 30.
            * basis_order (int, optional): Basis order. Defaults to -1.

        Returns:
            int: The return code of status.
                * 0 Setup of "Sweep_em_setup" added to design with setup_args. 
                * 1 Look at warning message to determine which argument was of 
                  the wrong data type.
                * 2 Look at warning message, a key in setup_args that was 
                  not expected.
        """

        a_hfss = self.design.renderers.hfss
        setup_args.name = "Sweep_em_setup"
        a_hfss.pinfo.design.delete_setup(setup_args.name)

        for key, value in setup_args.items():
            if key == "name":
                continue  #For this method, "Sweep_em_setup" used.
            if key == "min_freq_ghz":
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == "n_modes":
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == "max_delta_f":
                if isinstance(value, float) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "float")
                    return 1
            if key == 'max_passes':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'min_passes':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'min_converged':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'basis_order':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'pct_refinement':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1

            self.design.logger.warning(
                f'The key={key} is not expected.  Do you have a typo?  '
                f'The setup was not added to design. '
                f'Sweep will not be implemented.')
            return 2

        a_hfss.add_eigenmode_setup(**setup_args)
        a_hfss.activate_eigenmode_setup(setup_args.name)
        return 0

    def warning_for_setup(self, setup_args: dict, key: str, data_type: str):
        """Give a warning based on key/value of dict.

        Args:
            setup_args (dict): Holds the key/value of setup arguments 
                        that are of interest.
            key (str): Name of setup argument.
            data_type (str): The data type the argument should be. 
        """
        self.design.logger.warning(
            f'The value for {key} should be a {data_type}. '
            f'The present value is {setup_args[key]}.  '
            f'Sweep will not be implemented.')

    def prep_q3d_setup(self, setup_args: Dict) -> int:
        """User can pass arguments for method q3d setup.  If not passed, 
        method will use the options in Q3D renderer default_options. 
        The name of setup will be "Sweep_q3d_setup".  If a setup named 
        "Sweep_q3d_setup" exists in the project, it will be deleted, and 
        a new setup will be added with the arguments from setup_args. 

        Assume: Error checking has already occurred for existence of Ansys, 
        project, and Q3d Extractor design has been connected to pinfo.

        Args:
            setup_args (Dict): Maximum  keys used in setup_args.

        **setup_args** dict contents:
            * freq_ghz (float, optional): Frequency in GHz. Defaults to 5..
            * name (str, optional): Name of solution setup. 
                        Defaults to "Setup".
            * max_passes (int, optional): Maximum number of passes. 
                        Defaults to 15.
            * min_passes (int, optional): Minimum number of passes. 
                        Defaults to 2.
            * percent_error (float, optional): Error tolerance as percentage. 
                        Defaults to 0.5.
            * save_fields (bool, optional): Whether or not to save fields. 
                        Defaults to False.
            * enabled (bool, optional): Whether or not setup is enabled. 
                        Defaults to True.
            * min_converged_passes (int, optional): Minimum number of 
                        converged passes. Defaults to 2.
            * percent_refinement (int, optional): Refinement as a percentage. 
                        Defaults to 30.
            * auto_increase_solution_order (bool, optional): Whether or not 
                        to increase solution order automatically. 
                        Defaults to True.
            * solution_order (str, optional): Solution order. 
                        Defaults to 'High'.
            * solver_type (str, optional): Solver type. 
                        Defaults to 'Iterative'.

        Returns:
            int:  The return code of status.
                * 0 Setup of "Sweep_q3d_setup" added to design with setup_args.
                * 1 Look at warning message to determine which argument was 
                        of the wrong data type.
                * 2 Look at warning message, a key in setup_args that was not 
                        expected.
        """
        a_q3d = self.design.renderers.q3d
        setup_args.name = "Sweep_q3d_setup"
        a_q3d.pinfo.design.delete_setup(setup_args.name)

        for key, value in setup_args.items():
            if key == "name":
                continue  #For this method, "Sweep_q3d_setup" used.
            if key == "freq_ghz":
                if isinstance(value, float) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "float")
                    return 1
            if key == 'max_passes':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'min_passes':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'percent_error':
                if isinstance(value, float) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "float")
                    return 1
            if key == 'save_fields':
                if isinstance(value, bool) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "bool")
                    return 1
            if key == 'enabled':
                if isinstance(value, bool) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "bool")
                    return 1
            if key == 'min_converged_passes':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'percent_refinement':
                if isinstance(value, int) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "int")
                    return 1
            if key == 'auto_increase_solution_order':
                if isinstance(value, bool) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "bool")
                    return 1
            if key == 'solution_order':
                if (isinstance(value, str) and
                        value in ["High", "Normal", "Higher", "Highest"
                                 ]) or value is None:
                    continue
                else:
                    self.design.logger.warning(
                        f'The value for solution_order should be a str '
                        f'in ["High", "Normal", "Higher", "Highest"]. '
                        f'The present value is {value}.  '
                        f'Sweep will not be implemented.')
                    return 1
            if key == 'solver_type':
                if isinstance(value, str) or value is None:
                    continue
                else:
                    self.warning_for_setup(setup_args, key, "str")
                    return 1

            self.design.logger.warning(
                f'The key={key} is not expected.  Do you have a typo?  '
                f'The setup was not added to design. '
                f'Sweep will not be implemented.')
            return 2

        a_q3d.add_q3d_setup(**setup_args)
        a_q3d.activate_q3d_setup(setup_args.name)
        return 0

    def sweep_one_option_get_eigenmode_solution_data(
            self,
            qcomp_name: str,
            option_name: str,
            option_sweep: list,
            qcomp_render: list,
            endcaps_render: list,
            ignored_jjs_render: list,
            box_plus_buffer_render: bool = True,
            setup_args: Dict = None,
            leave_last_design: bool = True,
            design_name: str = "Sweep_Eigenmode") -> Tuple[dict, int]:
        """
        Ansys must be open with inserted project. A design, "HFSS Design"
        with eigenmode solution-type will be inserted by this method.

        Args:
            qcomp_name (str): A component that contains the option to be 
                                swept. Assume qcomp_name is in qcomp_render.
            option_name (str): The option within qcomp_name to sweep.
                                Follow details from 
                                renderer in QHFSSRenderer.render_design.
            option_sweep (list): Each entry in the list is a value for 
                                option_name.
            qcomp_render(list): List of components to render to Ansys.
            endcaps_render (list): Identify which kind of pins. 
                                    Follow details from renderer in
                                    QHFSSRenderer.render_design.
            ignored_jjs_render (list): List of tuples of jj's that shouldn't  
                                    be rendered.  Follow details from 
                                    renderer in QHFSSRenderer.render_design.
            box_plus_buffer_render (bool): Either calculate a bounding box  
                                    based on the location of rendered  
                                    geometries or use chip size from design 
                                    class.  Follow details from renderer in
                                    QHFSSRenderer.render_design.  
                                    Default is True.
            setup_args (Dict): Hold the arguments for  Hfss eigenmode setup() 
                                    as  key/values to pass to Ansys.  
                                    If None, default Setup will be used.
            leave_last_design (bool): In HFSS, after the last sweep, 
                                    should the design be cleared? 
                                    Default is True.
            design_name (str, optional):  Name of HFSS_design to use in 
                                    project. Defaults to "Sweep_Eigenmode".

        Returns:
            Tuple[dict, int]: The dict key is each value of option_sweep, the value is
            the solution-data for each sweep.
            The int is the o bservation of searching for data from arguments as defined below.

            * 0 Have list of capacitance matrix.
            * 1 qcomp_name not registered in design.
            * 2 option_name is empty.
            * 3 option_name is not found as key in dict.
            * 4 option_sweep is empty, need at least one entry.
            * 5 last key in option_name is not in dict.
            * 6 project not in app
            * 7 design not in app
            * 8 setup not implement, check the setup_args.
        """

        #Dict of all swept information.
        all_sweep = dict()
        option_path, a_value, check_result, = self.error_check_sweep_input(
            qcomp_name, option_name, option_sweep)
        if check_result != 0:
            return all_sweep, check_result

        a_hfss = self.design.renderers.hfss
        # Assume Ansys is open, with a project open.
        a_hfss.connect_ansys()
        a_hfss.activate_eigenmode_design(design_name)

        a_hfss.clean_active_design()

        if self.prep_eigenmode_setup(setup_args) != 0:
            self.design.logger.warning(
                f'The setup was not implemented, look at warning messages.')
            return all_sweep, 8

        len_sweep = len(option_sweep) - 1

        for index, item in enumerate(option_sweep):
            if option_path[-1] in a_value.keys():
                a_value[option_path[-1]] = item
            else:
                self.design.logger.warning(
                    f'Key="{option_path[-1]}" is not in dict.')
                return all_sweep, 5

            self.design.rebuild()

            a_hfss.render_design(selection=qcomp_render,
                                 open_pins=endcaps_render,
                                 ignored_jjs=ignored_jjs_render,
                                 box_plus_buffer=box_plus_buffer_render
                                )  #Render the items chosen

            a_hfss.analyze_setup(
                a_hfss.pinfo.setup.name)  #Analyze said solution setup.
            setup = a_hfss.pinfo.setup
            #solution_name = setup.solution_name
            all_solutions = setup.get_solutions()
            #setup_names = all_solutions.list_variations()
            freqs, kappa_over_2pis = all_solutions.eigenmodes()

            sweep_values = dict()
            sweep_values['option_name'] = option_path[-1]
            sweep_values['frequency'] = freqs
            sweep_values['kappa_over_2pis'] = kappa_over_2pis
            sweep_values['quality_factor'] = self.get_quality_factor(
                freqs, kappa_over_2pis)
            all_sweep[item] = sweep_values

            #Decide if need to clean the design.
            obj_names = a_hfss.pinfo.get_all_object_names()
            if obj_names:
                if index == len_sweep and not leave_last_design:
                    a_hfss.clean_active_design()
                elif index != len_sweep:
                    a_hfss.clean_active_design()

        a_hfss.disconnect_ansys()
        return all_sweep, 0

    def get_quality_factor(
            self,
            freqs: Union[list, None] = None,
            kappa_over_2pis: Union[list, None] = None) -> Union[list, None]:
        """Calculate Quality Factor = freqs/kappa_over_2pis.  Before division, some error checking. 

        Args:
            freqs (Union[list, None], optional): The eigenmode frequency. Defaults to None.
            kappa_over_2pis (Union[list, None], optional): The kappa/(2*pi) Defaults to None.

        Returns:
            Union[list, None]: Calculate freqs/kappa_over_2pis
        """

        quality_factor = None
        if kappa_over_2pis is None:
            return quality_factor

        # Asssume both are lists or None since method:  eigenmodes() in pyEPR returns a list or None.
        if len(freqs) == len(kappa_over_2pis):
            quality_factor = [
                float(ff) / float(kk) for ff, kk in zip(freqs, kappa_over_2pis)
            ]
            return quality_factor
        else:
            self.design.logger.warning(
                'The Quality factor not calculated since size of freqs and kappa_over_2pis are not identical'
            )
            return quality_factor

    def sweep_one_option_get_capacitance_matrix(
            self,
            qcomp_name: str,
            option_name: str,
            option_sweep: list,
            qcomp_render: list,
            endcaps_render: list,
            setup_args: Dict = None,
            leave_last_design: bool = True,
            design_name: str = "Sweep_Capacitance") -> Tuple[dict, int]:
        """Ansys must be open with an inserted project.  A design, 
        "Q3D Extractor Design", will be inserted by this method.

        Args:
            qcomp_name (str): A component that contains the option to be swept.
            option_name (str): The option within qcomp_name to sweep.
            option_sweep (list): Each entry in the list is a value for 
                        option_name.
            qcomp_render (list): The component to render to Q3D. 
            endcaps_render (list): Identify which kind of pins. Follow the 
                        details from renderer QQ3DRenderer.render_design.
            setup_args (Dict): Hold the arguments for  Q3d setup() as  
                        key/values to pass to Ansys.  
                        If None, default Setup will be used.
            leave_last_design (bool) : In Q3d, after the last sweep, should 
                        the design be cleared?
            design_name(str): Name of q3d_design to use in project.

        Returns:
            dict or int: If dict, the key is each value of option_sweep, the value is 
            the capacitance matrix for each sweep.
            If int, observation of searching for data from arguments as defined below

            * 0 Have list of capacitance matrix.
            * 1 qcomp_name not registered in design.
            * 2 option_name is empty.
            * 3 option_name is not found as key in dict.
            * 4 option_sweep is empty, need at least one entry.
            * 5 last key in option_name is not in dict.
            * 6 project not in app
            * 7 design not in app
            * 8 setup not implement, check the setup_args. 
           
        """
        #Dict of all swept information.
        all_sweep = dict()
        option_path, a_value, check_result = self.error_check_sweep_input(
            qcomp_name, option_name, option_sweep)
        if check_result != 0:
            return all_sweep, check_result

        a_q3d = self.design.renderers.q3d
        # Assume Ansys is open, with a project open.
        a_q3d.connect_ansys()
        a_q3d.activate_q3d_design(design_name)

        a_q3d.clean_active_design()

        # Add a solution setup.
        if self.prep_q3d_setup(setup_args) != 0:
            self.design.logger.warning(f'The setup was not implemented, '
                                       f'please look at warning messages.')
            return all_sweep, 8

        len_sweep = len(option_sweep) - 1

        # Last item in list.
        for index, item in enumerate(option_sweep):
            if option_path[-1] in a_value.keys():
                a_value[option_path[-1]] = item
            else:
                self.design.logger.warning(
                    f'Key="{option_path[-1]}" is not in dict.')
                return all_sweep, 5

            self.design.rebuild()

            a_q3d.render_design(
                selection=qcomp_render,
                open_pins=endcaps_render)  #Render the items chosen

            a_q3d.analyze_setup(
                a_q3d.pinfo.setup.name)  #Analyze said solution setup.
            cap_matrix = a_q3d.get_capacitance_matrix()

            sweep_values = dict()
            sweep_values['option_name'] = option_path[-1]
            sweep_values['capacitance'] = cap_matrix
            all_sweep[item] = sweep_values

            #Decide if need to clean the design.
            obj_names = a_q3d.pinfo.get_all_object_names()
            if obj_names:
                if index == len_sweep and not leave_last_design:
                    a_q3d.clean_active_design()
                elif index != len_sweep:
                    a_q3d.clean_active_design()

        a_q3d.disconnect_ansys()
        return all_sweep, 0

    # The methods allow users to sweep a variable in a components's options.
