'''
.. module:: kf.detailed

    :synopsis: LKFFB implementation with detailed data retention of key Kalman
        state variables and derived quantities. Facilitates exploration of different
        Prediction methods ('ZeroGain' or 'PropForward') and maximallly generic choices
        of apriori basis for LKFFB (Basis 'A', 'B', or 'C').

    Module Level Functions:
    ----------------------
        makePropForward : Return learned parameters from
            msmt_record via LKFFB and make predictions for timesteps > n_train.
        detailed_kf : Return LKFFB predictions and spectral amplitude information
            and save LKFFB analysis as .npz file.

.. moduleauthor:: Riddhi Gupta <riddhi.sw@gmail.com>

'''

import numpy as np
#import numba as nb
import numpy.linalg as la

from kf.common import calc_inst_params, calc_pred, calc_Gamma, get_dynamic_model, propagate_states, calc_Kalman_Gain, calc_residuals


def makePropForward(freq_basis_array, x_hat, Delta_T_Sampling, phase_correction_noisetraces, num, n_train, numf):
    ''' Extracts learned parameters from Kalman Filtering msmt_record and makes
        predictions for timesteps > n_train.

    Parameters:
    ----------
        freq_basis_array (`float64`): Array containing `numf` number of basis frequencies.
        x_hat (`float64`): Aposteriori KF estimates based on msmt_record.
        Delta_T_Sampling (`float64`): Time interval between measurements.
        phase_correction_noisetraces (`float64`): Applies depending on choice of basis
        num (`int`): Number of points in msmt_record.
        n_train (`int`): Predicted timestep at which algorithm is expected to finish learning.
        numf (`int`): Number of points (spectral basis frequencies) in freq_basis_array.

    Returns:
    -------
        Propagate_Foward (`float64`): Output predictions. Non-zero only
            for n_train < timestep < num.
        instantA (`float64`): Instantaneous amplitude calculated based on
            estimated state x_hat [Dim: numf x num]
        instantP (`float64`): Instantaneous phase calculated based on estimated
            state x_hat [Dim: numf x num]
    '''
    # Instantaneous Amplitude, Phase and Frequency Calculations
    # # not optimised as it doesn't concern the loop
    instantA = np.zeros((numf, num))
    instantP = np.zeros((numf, num))
        ## CALCULATE INSTANTANEOUS PHASE, AMPLITUDE AND FREQUENCY
    k = 1
    while (k < num):
        instantA[:, k], instantP[:, k] = calc_inst_params(x_hat[:, :, k])
        k = k + 1

    ## PROPAGATE FORWARD USING HARMONIC SUMS
    Propagate_Foward = np.zeros((num))
    instantA_Prediction = instantA[:, n_train]
    instantP_Prediction = instantP[:, n_train]

    # Using a harmonic sum for propagating the noise
    tn = 0
    for tn in range(n_train,num,1):
        Propagate_Foward[tn] = instantA_Prediction[0]*np.cos((Delta_T_Sampling*tn*freq_basis_array[0]*2*np.pi + instantP_Prediction[0]))
        Propagate_Foward[tn] += np.sum(instantA_Prediction[1:]*np.cos((Delta_T_Sampling*tn*freq_basis_array[1:]*2*np.pi + instantP_Prediction[1:] + phase_correction_noisetraces))) # with correction for noise traces 

    return Propagate_Foward, instantA, instantP


def detailed_kf(descriptor, y_signal, n_train, n_testbefore, n_predict,
                Delta_T_Sampling, x_hat_initial,P_hat_initial, oekalman, rkalman,
                freq_basis_array, phase_correction, skip_msmts=1): 
    ''' Return LKFFB predictions and spectral amplitude information and save LKFFB analysis
        as .npz file.
    
    Known Information for Filter Design:
    ------------------------------------
    a -- Linearised dynamic model - time invariant [Dim: twonumf x twonumf. dtype = float64]
    h -- Linear measurement action - time invariant [Dim: 1 x twonumf x num. dtype = float64]
    Gamma2, Gamma -- Process noise features [Dim: twonumf x 1 x num. dtype = float64]
    Q -- Process noise covariance.[Dim: twonumf x twonumf x num. dtype = float64]
    R -- Measurement noise covariance; equivalent to rkalman for scalar measurement
        noise. [Dim: 1 x 1 x num. dtype = float64]

    Variables for State Estimation and State Covariance Estimation:
    ---------------------------------------------------------------
    x_hat -- Estimated real and estimated imaginary components of state
        [Dim: twonumf x 1 x num. dtype = float64].
    z_proj -- Apriori predicted measurement [Dim: 1 x 1 x num. dtype = float64]
    e_z -- Residuals, i.e. z - z_proj [Dim: 1 x 1 x num. dtype = float64]
    S --  Predicted output covariance estimate (i.e. uncertainty in  z_proj)
         [Dim: 1 x 1 x num. dtype = float64].
    S_inv -- Inverse of S (NB: R must be a positive definite if S is not Scalar)
         [Dim: 1 x 1 x num. dtype = float64].
    W -- Kalman gain [Dim: twonumf x 1 x num. dtype = float64]
    P_hat -- State covariance estimate (i.e. uncertainty in estimated x_hat)
    [Dim: twonumf x twonumf x num. dtype = float64].

    Parameters:
    ----------
        y_signal (`float64`): Array containing measurements for Kalman Filtering. [Dim: 1 x 1 x num]
        n_train (`int`): Timestep at which algorithm is expected to finish learning.
        n_testbefore (`int`): Number of on step ahead predictions prior to n_train
            which user requires to be returned as output.
        n_predict (`int`): Predictions outside of msmt data.
        Delta_T_Sampling (`float64`): Time interval between measurements.
        x_hat_initial (`float64`): Initial conditions for state estimate, x(0),
            for all basis frequencies.
        P_hat_initial (`float64`): Initial conditions for state covariance estimate,
            P(0), for all basis frequencies.
        oekalman (`float64`): Process noise covariance strength.
        rkalman (`float64`): Measurement noise covariance strength.
        freq_basis_array (`float64`): Array containing `numf` number of basis frequencies.
        phase_correction (`float64`): Applies if y_signal data are Ramsey frequency
            offset measurements.
        skip_msmts ('int'): Allow a non zero Kalman gain for every n-th msmt,
            where skip_msmts == n and skip_msmts=1 implies all measurements
            can have a non-zero gain.

    Returns:
    --------
        predictions (`float64`) : Output predictions [len: n_testbefore + n_predict].
        InstantA (`float64`): Instantaneous amplitudes at n_train use for generating
            predictions using Prop Forward [len: numf].

    Dimensions:
    -----------
        num (`int`): Number of points in y_signal.
        numf (`int`): Number of points (spectral basis frequencies) in freq_basis_array.
        twonumf (`int`): 2*numf. (NB: For each basis freq in freq_basis_array,
            estimators have a real and imaginary parts).
    '''
    phase_correction_noisetraces = phase_correction
    predictions = np.zeros(n_testbefore + n_predict)

    # Model Dimensions
    num = n_predict + n_train
    numf = len(freq_basis_array)
    twonumf = int(numf*2.0)

    # Kalman Measurement Data
    z = np.zeros((1, 1, num))
    z[0, 0, :] = y_signal

    # State Estimation
    x_hat = np.zeros((twonumf, 1, num))
    e_z = np.zeros((1, 1, num))
    P_hat = np.zeros((twonumf, twonumf, num))

    # Dynamical Model
    a = get_dynamic_model(twonumf, Delta_T_Sampling, freq_basis_array, coswave=-1)

    # Measurement Action
    h = np.zeros((1, twonumf, num))
    h[0, ::2, ...] = 1.0

    # Initial Conditions
    x_hat[:, 0, 0] = x_hat_initial
    diag_indx = range(0, twonumf, 1)
    P_hat[diag_indx, diag_indx, 0] = P_hat_initial

    # Noise Features
    Q = np.zeros((twonumf, twonumf, num))
    R = np.ones((1, 1, num))
    R[0, 0, :] = rkalman

    # Covariance Estimation
    S = np.zeros((1, 1, num))
    S_inv = np.zeros((1, 1, num))
    W = np.zeros((twonumf, 1, num))

    store_S_Outer_W = np.zeros((twonumf, twonumf, num))

    k = 1
    while (k< n_train+1):

        x_hat[:, :, k], P_hat[:, :, k], Q[:, :, k] = propagate_states(a, x_hat[:, :, k-1], P_hat[:, :, k-1], oekalman, numf)

        W[:, :, k], S[:, :, k] = calc_Kalman_Gain(h[:, :, k], P_hat[:, :, k], rkalman)

        # Skp Msmts
        if k % skip_msmts != 0:
            W[:, :, k] = np.zeros_like(W[:, :, k]) #skipped msmt, model evolves with no new info.

        e_z[0, 0, k] = calc_residuals(h[:, :, k], x_hat[:, :, k], z[0, 0, k])

        #print 'Aposteriori Updates'
        x_hat[:, :, k] = x_hat[:, :, k] + W[:, :, k]*e_z[0, 0, k]
        store_S_Outer_W[:, :, k] = S[:, :, k]*np.outer(W[:, :, k], W[:, :, k].T)

        # For scalar S
        P_hat[:, :, k] = P_hat[:, :, k] - S[:, :, k]*np.outer(W[:, :, k], W[:, :, k].T)

        k = k + 1

    # We report one step ahead predictions for n < n_train
    predictions[0:n_testbefore] = calc_pred(x_hat[:, :, n_train-n_testbefore:n_train])

    # We use Prop Forward to "forecast" for n> n_train
    Propagate_Foward, instantA, instantP = makePropForward(freq_basis_array, x_hat, Delta_T_Sampling, phase_correction_noisetraces, num, n_train, numf)
    predictions[n_testbefore:] = Propagate_Foward[n_train:]

    np.savez(str(descriptor),
             descriptor=descriptor,
             predictions=predictions,
             y_signal=y_signal,
             freq_basis_array=freq_basis_array,
             x_hat=x_hat,
             P_hat=P_hat,
             a=a,
             h=h,
             z=z,
             e_z=e_z,
             W=W,
             Q=Q,
             store_S_Outer_W=store_S_Outer_W,
             S=S,
             instantA=instantA,
             instantP=instantP,
             oe=oekalman,
             rk=rkalman,
             n_train=n_train,
             n_predict=n_predict,
             n_testbefore=n_testbefore,
             skip_msmts=skip_msmts,
             Propagate_Foward=Propagate_Foward,
             phase_correction=phase_correction_noisetraces)

    return predictions, instantA[:, n_train]
