import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mtick


from analysis_tools.case_data_explorer import CaseExplorer as cs

# Import figure making dictionaries and parameters
from analysis_tools.testcaseDict import tcDict
from analysis_tools.testcaseFigstyle import *
from analysis_tools.testcaseParams import *

path_to_directory = sys.argv[1]
dict_key = sys.argv[2]
savefigname = dict_key

test_case_list = tcDict[dict_key][0]
variation_list = tcDict[dict_key][1]
dial = tcDict[dict_key][2]
dial_label = tcDict[dict_key][3]
n_predict_list = tcDict[dict_key][4]
n_testbefore_list = tcDict[dict_key][5]
tagline = tcDict[dict_key][6]
loss_hist_min = float(tcDict[dict_key][7])
loss_hist_max = float(tcDict[dict_key][8])
amp_PSD_min = float(tcDict[dict_key][9])

NUM_SCENARIOS = len(test_case_list) 

for idx in xrange(NUM_SCENARIOS):
        vars()['obj_'+str(test_case_list[idx])+'_'+str(variation_list[idx])] = cs(
            test_case_list[idx],
            variation_list[idx],
            skip_list[idx],
            max_forecast_loss_list[idx],
            path_to_directory)

########################################
# FIG: Grid Specs
########################################
ROWS = 4
gs = gridspec.GridSpec(ROWS, NUM_SCENARIOS ,
                       left=0.08, right=0.97, 
                       top=0.88, bottom=0.05, 
                       wspace=0.6, hspace=0.5)

fig = plt.figure(figsize=( 3.0*(NUM_SCENARIOS ), 3.2*4))

count=0

for idx in xrange((NUM_SCENARIOS)):
    for idx_ax2 in xrange(ROWS):
        if (idx==3 or idx==4) and (dict_key[0:2]=='tc' or dict_key=='st_2' or dict_key=='st_6'):
            vars()['ax_var'+str(variation_list[idx])+'_'+str(idx_ax2)] = fig.add_subplot(gs[idx_ax2, idx], facecolor='linen')
        else:
            vars()['ax_var'+str(variation_list[idx])+'_'+str(idx_ax2)] = fig.add_subplot(gs[idx_ax2, idx])
        #vars()['ax_var'+str(variation_list[idx])+'_'+str(idx_ax2)].locator_params(axis='x', numticks=4)

# Add custom legend for loss plots
vars()['ax_var'+str(variation_list[2])+'_'+str(0)].legend(handles=(randinit,  un_opt_traj,  pred_circ, fore_circ, optimalstar, opt_traj),
                                                                  labels= [r'Random Init. ($\sigma, R$)', 'Unoptimal Risk Traj.', 'Low State Est. Risk', 'Low Prediction Risk', r'Tuned ($\sigma, R$)',  'Optimal Risk Traj.'],
                                                                  bbox_to_anchor=(-3.8, 1.21, 5.0, 0.2), loc=2, ncol=6, frameon=True, fontsize=12.5,
                                                                  facecolor='linen',
                                                                  edgecolor='white')

########################################
# FIG: Loss Plots
########################################
idx_ax1_list = [0, 2] # Loss Map on 1st and 3rd rows
idx_ax2_list = [1, 3] # Loss Histogram on second and last rows

for idx in xrange(NUM_SCENARIOS):

    obj_ = 'obj_'+str(test_case_list[idx])+'_'+str(variation_list[idx])
    output = vars()[obj_].return_low_loss_hyperparams_list(truncation_=TRUNCATION) # this has data from kf and akf

    for idx_kf_type in xrange(2): 

        ########################################
        # Break data up into KF (idx_kf_type=0) and AKF (idx_kf_type=1)
        ########################################

        s0, R0, s1, R1, sigma, R, p_index, p_losses = [item for item in output[idx_kf_type]]

        ########################################
        # FIG: Loss Map (Sigma v. R)
        ########################################
        
        idx_ax1 = idx_ax1_list[idx_kf_type]       
        ax_ = vars()['ax_var'+str(variation_list[idx])+'_'+str(idx_ax1)]

        if idx==0:
            ax_.set_ylabel(r' Kalman $R$ [$f_n^2$]')
        if idx==2:
            ax_.set_xlabel(r' Kalman $\sigma $ [$x^2$]')
        
        ax_.set_xlim([10**-11,1000])
        ax_.set_ylim([10**-11,1000])
        ax_.set_xscale('log')
        ax_.set_yscale('log')
        ax_.plot(s0, R0, 'o', c='tan', markersize=25, alpha=0.7)
        ax_.plot(s1, R1, 'o', c='cyan', markersize=15, alpha=0.7)
        ax_.plot(sigma, R, 'kv', markersize=5, alpha=1.0)
        ax_.plot(s0[0], R0[0],'*', color=optimal_star, markersize=15, mew=2)
        ax_.tick_params(direction='in', which='both')

        if idx_ax1==0 :
            ax_.annotate(ax_kea_labels[idx] + ': ' + dial_label + ' = ' + str(np.round(dial[idx], 3)), xy=(-0.15, 1.45), 
                    xycoords=('axes fraction', 'axes fraction'),
                    xytext=(1,1),
                    textcoords='offset points',
                    size=14.5,
                    color=us_colour_list[idx],
                    ha='left',
                    va='center')

        if idx_ax1 == 0 and idx==0 :

            ax_.annotate(tagline, xy=(-0.5, 1.65), 
                    xycoords=('axes fraction', 'axes fraction'),
                    xytext=(1,1),
                    textcoords='offset points',
                    size=20,
                    color='k',
                    ha='left',
                    va='center')
     
            ax_.annotate('KF - Basis of Oscillators', xy=(-0.5, 1.06), 
                    xycoords=('axes fraction', 'axes fraction'),
                    xytext=(1,1),
                    textcoords='offset points',
                    size=fsize*1.05,
                    color='r',
                    ha='left',
                    va='center')
        
        if idx_ax1 == 2 and idx==0:     
            ax_.annotate('KF - Autoregressive AR(q=101) with LS Weights', xy=(-0.5, 1.08), 
                    xycoords=('axes fraction', 'axes fraction'),
                    xytext=(1,1),
                    textcoords='offset points',
                    size=fsize*1.05,
                    color='r',
                    ha='left',
                    va='center')
        
        ########################################
        # FIG: Loss Map on Variational Plots
        ########################################
        
        idx_ax2 = idx_ax2_list[idx_kf_type]
        ax_2 = vars()['ax_var'+str(variation_list[idx])+'_'+str(idx_ax2)]

        start_at = vars()[obj_].n_testbefore - n_testbefore_list[variation_list[idx]] #== 0 if Delta_T is not changing
        end_at = n_predict_list[variation_list[idx]] #==  n_predict if Delta_T is not changing
        
        x_axis = PLOT_SCALE*vars()[obj_].Delta_T_Sampling*np.arange(start_at - vars()[obj_].n_testbefore, end_at, 1)

        # Define the optimal trajectory
        opt_index = p_index[0]
        print('For Variation %s, Opt Index = %s' %(variation_list[idx], opt_index) )

        # Define {unoptimal trajectories} == {all trajectories} - {top X "optimally" lowest lost trajectories, X = truncation value}
        unopt_index_list = list(set(range(0, vars()[obj_].num_randparams, 1)) - set(p_index))

        count=0
        alpha=0.1

        # Choose dataset (KF v. AKF):
        PRED_DICT = {'0': np.mean(vars()[obj_].macro_prediction_errors, axis=1),
                     '1': np.mean(vars()[obj_].akf_macro_prediction_errors, axis=1)}
        FORE_DICT = {'0': np.mean(vars()[obj_].macro_forecastng_errors, axis=1), 
                     '1': np.mean(vars()[obj_].akf_macro_forecastng_errors, axis=1)}

        # Plot unoptimal trajectories from dataset:
        for chosen_index in unopt_index_list:
            ax_2.plot(x_axis[ : n_testbefore_list[variation_list[idx]] ], PRED_DICT[str(idx_kf_type)][chosen_index, start_at: ], 
                    '-', markersize=4, alpha=alpha, c='k')
            ax_2.plot(x_axis[ n_testbefore_list[variation_list[idx]] : ], FORE_DICT[str(idx_kf_type)][chosen_index, 0:end_at ], 
                    '-', markersize=4, alpha=alpha, c='k')
        
        # Plot optimal trajectories from dataset:
        alpha=0.5
        count=0
        for chosen_index in p_index[1:] + [opt_index]:
            if chosen_index==opt_index:
                count=2
                alpha=1.0
            ax_2.plot(x_axis[:n_testbefore_list[variation_list[idx]]], PRED_DICT[str(idx_kf_type)][chosen_index, start_at: ], 
                    style[count], 
                    markersize=4, alpha=1.0, c=loss_color_list[count])
            ax_2.plot(x_axis[n_testbefore_list[variation_list[idx]] :],FORE_DICT[str(idx_kf_type)][chosen_index, 0:end_at ], 
                    style[count+1], 
                    markersize=4, alpha=1.0, c=loss_color_list[count+1])
        

        ax_2.set_yscale('log')
        ax_2.set_xlim([-50,50])
        ax_2.set_ylim([loss_hist_min, loss_hist_max])
        ax_2.axvspan(-50,0, color='gray', alpha=0.3)
        
        if idx==0:
            ax_2.set_ylabel(r'log($\langle (f_n -\hat{f_n})^2 \rangle_D$) [log($f_n^2$)]')
        if idx==2:
            ax_2.set_xlabel('Stps Fwd [num]')
        
        ax_2.tick_params(direction='in', which='both')

######################################
# Font Sizes
######################################

for idx in xrange(NUM_SCENARIOS):
    for idx_ax2 in xrange(ROWS):
        ax = vars()['ax_var'+str(variation_list[idx])+'_'+str(idx_ax2)]
        for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontsize(fsize)
#        for item in ([ax.xaxis.label, ax.yaxis.label]):
#            item.set_weight('bold')

######################################
# Save and Close
######################################   
#    
fig.savefig(savefigname+'loss_comparison.png', format='png')
plt.close(fig)


