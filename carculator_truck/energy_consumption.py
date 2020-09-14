from .driving_cycles import get_standard_driving_cycle
from .gradients import get_gradients
import numexpr as ne
import numpy as np
import xarray as xr


def _(o):
    """Add a trailing dimension to make input arrays broadcast correctly"""
    if isinstance(o, (np.ndarray, xarray.DataArray)):
        return np.expand_dims(o, -1)
    else:
        return o


class EnergyConsumptionModel:
    """
    Calculate energy consumption of a vehicle for a given driving cycle and vehicle parameters.

    Based on a selected driving cycle, this class calculates the acceleration needed and provides
    two methods:

        - :func:`~energy_consumption.EnergyConsumptionModel.aux_energy_per_km` calculates the energy needed to power auxiliary services
        - :func:`~energy_consumption.EnergyConsumptionModel.motive_energy_per_km` calculates the energy needed to move the vehicle over 1 km

    Acceleration is calculated as the difference between velocity at t_2 and velocity at t_0, divided by 2.
    See for example: http://www.unece.org/fileadmin/DAM/trans/doc/2012/wp29grpe/WLTP-DHC-12-07e.xls

    :param cycle: Driving cycle. Pandas Series of second-by-second speeds (km/h) or name (str)
        of cycle e.g., "Urban delivery", "Regional delivery", "Long haul".
    :type cycle: pandas.Series
    :param rho_air: Mass per unit volume of air. Set to (1.225 kg/m3) by default.
    :type rho_air: float
    :param gradient: Road gradient per second of driving, in degrees. None by default. Should be passed as an array of
                    length equal to the length of the driving cycle.
    :type gradient: numpy.ndarray

    :ivar rho_air: Mass per unit volume of air. Value of 1.204 at 23C (test temperature for WLTC).
    :vartype rho_air: float
    :ivar velocity: Time series of speed values, in meters per second.
    :vartype velocity: numpy.ndarray
    :ivar acceleration: Time series of acceleration, calculated as increment in velocity per interval of 1 second,
        in meter per second^2.
    :vartype acceleration: numpy.ndarray


    """

    def __init__(self, cycle, rho_air=1.204):
        # If a string is passed, the corresponding driving cycle is retrieved
        if isinstance(cycle, str):
            try:
                self.cycle_name = cycle
                cycle = get_standard_driving_cycle(cycle)

            except KeyError:
                raise ("The driving cycle specified could not be found.")

        # if an array is passed instead, then it is used directly
        elif isinstance(cycle, np.ndarray):
            self.cycle_name = "custom"
            pass

        # if not, it's a problem
        else:
            raise ("The format of the driving cycle is not valid.")


        self.gradient_name = self.cycle_name
        # retrieve road gradients (in degress) for each second of the driving cycle selected
        self.gradient = get_gradients(self.gradient_name).reshape(-1,1,1,6)
        # reshape the driving cycle
        self.cycle = cycle.reshape(-1,1,1,6)

        self.rho_air = rho_air

        # Unit conversion km/h to m/s
        self.velocity = (self.cycle * 1000) / 3600

        # Model acceleration as difference in velocity between time steps (1 second)
        # Zero at first value
        self.acceleration = np.zeros_like(self.velocity)
        self.acceleration[1:-1] = (self.velocity[2:] - self.velocity[:-2]) / 2

    def aux_energy_per_km(self, aux_power, efficiency=1):
        """
        Calculate energy used other than motive energy per km driven.

        :param aux_power: Total power needed for auxiliaries, heating, and cooling (W)
        :type aux_power: int
        :param efficiency: Efficiency of electricity generation (dimensionless, between 0.0 and 1.0).
                Battery electric vehicles should have efficiencies of one here, as we account for
                battery efficiencies elsewhere.
        :type efficiency: float

        :returns: total auxiliary energy in kJ/km
        :rtype: float

        """

        distance = self.velocity.sum(axis=0)[0][0]
        # Provide energy in kJ / km (1 J = 1 Ws)
        auxiliary_energy = (
            aux_power.T  # Watt
            * self.velocity.shape[0]  # Number of seconds -> Ws -> J
            / distance  # m/s * 1s = m -> J/m
            * 1000  # m / km
            / 1000  # 1 / (J / kJ)
        )

        return (auxiliary_energy / efficiency).T

    def motive_energy_per_km(
        self,
        driving_mass,
        rr_coef,
        drag_coef,
        frontal_area,
        ttw_efficiency,
        recuperation_efficiency=0,
        motor_power=0,
        debug_mode=False
    ):
        """
        Calculate energy used and recuperated for a given vehicle per km driven.

        :param driving_mass: Mass of vehicle (kg)
        :type driving_mass: int
        :param rr_coef: Rolling resistance coefficient (dimensionless, between 0.0 and 1.0)
        :type rr_coef: float
        :param drag_coef: Aerodynamic drag coefficient (dimensionless, between 0.0 and 1.0)
        :type drag_coef: float
        :param frontal_area: Frontal area of vehicle (m2)
        :type frontal_area: float
        :param ttw_efficiency: Efficiency of translating potential energy into motion (dimensionless, between 0.0 and 1.0)
        :type ttw_efficiency: float
        :param recuperation_efficiency: Fraction of energy that can be recuperated (dimensionless, between 0.0 and 1.0). Optional.
        :type recuperation_efficiency: float
        :param motor_power: Electric motor power (watts). Optional.
        :type motor_power: int

        Power to overcome rolling resistance is calculated by:

        .. math::

            g v M C_{r}

        where :math:`g` is 9.81 (m/s2), :math:`v` is velocity (m/s), :math:`M` is mass (kg),
        and :math:`C_{r}` is the rolling resistance coefficient (dimensionless).

        Power to overcome air resistance is calculated by:

        .. math::

            \frac{1}{2} \rho_{air} v^{3} A C_{d}


        where :math:`\rho_{air}` is 1.225 (kg/m3), :math:`v` is velocity (m/s), :math:`A` is frontal area (m2), and :math:`C_{d}`
        is the aerodynamic drag coefficient (dimensionless).

        :returns: net motive energy (in kJ/km)
        :rtype: float

        """

        # Convert to km; velocity is m/s, times 1 second
        distance = self.velocity.sum(axis=0)[0][0] / 1000

        ones = np.ones_like(self.velocity)

        # Resistance from the tire rolling: rolling resistance coefficient * driving mass * 9.81
        rolling_resistance = (driving_mass * rr_coef * 9.81).T * ones
        # Resistance from the drag: frontal area * drag coefficient * air density * 1/2 * velocity^2
        air_resistance = (frontal_area * drag_coef * self.rho_air / 2).T * np.power(self.velocity, 2)
        # Resistance from road gradient: driving mass * 9.81 * sin(gradient)
        gradient_resistance = (driving_mass * 9.81).T * np.sin(self.gradient)
        # Inertia: driving mass * acceleration
        inertia = self.acceleration * driving_mass.values.T
        # Braking loss: when inertia is negative
        braking_loss = np.where(inertia <0, inertia *-1, 0)

        total_resistance = rolling_resistance + air_resistance + gradient_resistance + inertia

        if debug_mode==False:

            # Power required: total resistance * velocity
            total_power = total_resistance * self.velocity
            total_power = np.clip(total_power, 0, None)
            # Recuperation of the braking power within the limit of the electric engine power
            recuperated_power = (braking_loss * recuperation_efficiency.values.T) * self.velocity
            recuperated_power = np.clip(recuperated_power, 0, motor_power.values.T*1000)

            # Subtract recuperated power from total power, if any
            total_power -= recuperated_power
            # Total power per driving cycle to total power per km
            total_power /= distance
            # From power required at the wheels to power required by the engine
            total_power /= ttw_efficiency.values.T
            # From joules to kilojoules
            total_power /= 1000

            return total_power

        # if `debug_mode` == True, returns instead
        # the power to overcome rolling resistance, air resistance, gradient resistance,
        # inertia and braking resistance, as well as the total power and the energy to overcome it.
        else:
            rolling_resistance *= (self.velocity )
            air_resistance *= (self.velocity )
            gradient_resistance *= (self.velocity )
            inertia *= (self.velocity )
            braking_loss *= (self.velocity )
            total_power = total_resistance * (self.velocity)
            total_power = np.clip(total_power, 0, None)

            energy = total_power / ttw_efficiency.values.T

            energy /= 1000

            return (xr.DataArray(rolling_resistance.values, dims=["values", "year", "powertrain", "size"]),
                    xr.DataArray(air_resistance.values, dims=["values", "year", "powertrain", "size"]),
                    xr.DataArray(gradient_resistance.values, dims=["values", "year", "powertrain", "size"]),
                    xr.DataArray(inertia, dims=["values", "year", "powertrain", "size"]),
                    xr.DataArray(braking_loss, dims=["values", "year", "powertrain", "size"]),
                    xr.DataArray(total_power.values, dims=["values", "year", "powertrain", "size"]),
                    xr.DataArray(energy.values, dims=["values", "year", "powertrain", "size"]))

