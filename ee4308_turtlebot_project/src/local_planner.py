#!/usr/bin/env python

"""
    See turtlebot_control.cpp in `/doc` for a C++ implementation of PI controller from Lab2
    
    TODO:
    - add the map parameters (wall, height, width) in a ros_param server
    - generate map and path for RViz
    - change this simple node to an action node in order to allow the goal to be sent from RViz
"""

import rospy
from import math import atan2, sqrt, pow, pi
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, Vector3
from tf.transformation import euler_from_quaternion

from global_planner import AStar as pathSearch, globalSmoothing

# MAP PARAMETERS
local_smoothing = True
known_map = True
width   = 9
height  = 9
start   = (0,0)
goal    = (4,4)
walls = [(0.5,0),
         (0.5,2),
         (0.5,3),
         (1.5,0),
         (1.5,1),
         (3.5,0),
         (3.5,1),
         (3.5,2),
         (3.5,3),
         (3.5,4)]

# CONTROL PARAMETERS
TOL_ORIENT  = 0.001
TOL_DIST    = 0.1
K_p_orient	= 1
K_p_dist	= 0.1
K_i_orient	= 5e-4
K_i_dist	= 2e-5

# SMOOTHING PARAMETERS
SMOOTH_NB_PTS   = 2
SMOOTH_WEIGHTS  = [3, 1]

class CtrlStates:
    Orient, Move, Wait = range(3)


class LocalPlanner:

    def __init__(self):
        rospy.Subscriber("/odom_true", Odometry, self.makePlan)
        self.pub = rospy.Publisher("/cmd_vel_mux/input/teleop", Odometry, queue_size=1)
        
        # TODO: check exception is no path is found
        self.path = pathSearch(start, goal, walls, width, height)
        if not local_smoothing:
            self.path = globalSmoothing(self.path, 0.7)
        self.pts_cnt = 1
        self.ctrl_state = CtrlStates.Orient
        
        self.sum_theta = 0.
        self.sum_dist = 0.
        
        rospy.spin()


    def makePlan(self, odom):
        # Extract relevant state variable from Odometry message
        euler = euler_from_quaternion(odom.pose.pose.orientation)
        theta = euler[2]
        pos_x = odom.pose.pose.position.x
        pos_y = odom.pose.pose.position.y

        v_lin = 0.
        v_ang = 0.
        
        # Control intial orentation
        if self.ctrl_state == CtrlStates.Orient :
            # Compute orientation error
            (x,y) = self.path[self.pts_cnt]
            goal_theta = atan2(y-pos_y,x-pos_x)
            err_theta = self.checkAngle(goal_theta - theta)
    
            # Check if satisfactory => start motion
            if err_theta < TOL_ORIENT :
                self.ctrl_state = CtrlStates.Move
                self.sum_theta = 0.
                self.sum_dist = 0.
            # Else adjust orientation
            else:
                sum_theta += err_theta
                v_ang = K_p_orient*err_theta + K_i_orient*self.sum_theta
        
        # Control motion between waypoints
        elif self.ctrl_state == CtrlStates.Move :
            # Check if apply local smoothing or used global one
            if local_smoothing:
                nb_err_pts = SMOOTH_NB_PTS
            else:
                nb_err_pts = 1
            
            # Compute orientation and distance error for the next points
            err_theta = []
            err_dist = []
            for (x,y) in self.path[self.pts_cnt:self.pts_cnt+nb_err_pts]:
                err_theta_raw = atan2(y-pos_y,x-pos_x) - theta
                err_theta.append(self.checkAngle(err_theta_raw))
                err_dist.append(sqrt(pow(x-pos_x,2)+pow(y-pos_y,2)))
        
            # TODO:
            # - check if any point is under the tolerance -> shift pts_cnt
            # - computer v_lin and v_ang with a defined PI control law
            
            if err_dist[0] < TOL_DIST :
                if self.pts_cnt == (len(self.path) - 1):
                    self.ctrl_state = CtrlStates.Wait
                else:
                    self.pts_cnt += 1
                    self.sum_theta = 0. # should we reset the controller or not ?
                    self.sum_dist = 0.
                    # should be try a new iteration with the next points ?
            else:
                # try P-controller first, implement I later
                
                if local_smoothing:
                    err_theta_tot = 0
                    err_theta_scaling = 0
                    err_dist_tot = 0
                    err_dits_scaling = 0
                    for i in range(len(err_theta)):
                        err_theta_tot += err_theta[i]*err_dist[i]*SMOOTH_WEIGHTS[i]
                        err_theta_scaling += err_dist[i]*SMOOTH_WEIGHTS[i]
                        err_dist_tot += err_dist[i]*SMOOTH_WEIGHTS[i]
                        err_dits_scaling += SMOOTH_WEIGHTS[i]
                    err_theta_tot /= err_theta_scaling
                    err_dist_tot /= err_dist_scaling
                else:
                    err_theta_tot = err_theta[0]
                    err_dist_tot = err_dist[0]
                    
                    #sum_theta += err_theta[0]
                    #sum_dist += err_dist[0]
                
                vel_z = K_p_orient*err_theta_tot    #+ K_i_orient*sum_theta
                vel_x = K_p_dist*err_dist_tot       #+ K_i_dist*sum_dist
        
        # Wait for a new goal point
        else:
            pass
        
        cmd = Twist()
        cmd.linear.x = v_lin
        cmd.angular.z = v_ang
        self.pub.publish(cmd)


    def checkAngle(self, theta):
        if theta > pi:
            return(theta - 2*pi)
        if theta < -pi:
            return(theta + 2*pi)
        else:
            return(theta)


if __name__ == "__main__":
    rospy.init_node("local_planner", anonymous=True)
    try:
        node = Local_planner()
    except rospy.ROSInterruptException:
        rospy.loginfo("Shutting down node: %s", rospy.get_name())

