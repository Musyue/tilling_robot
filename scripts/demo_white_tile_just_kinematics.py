#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import String
from std_msgs.msg import Empty
from ur5_kinematics import *
import numpy
import time
"""
rosrun rosserial_python serial_node.py /dev/ttyUSB0
rostopic pub /toggle_led std_msgs/Empty "{}" --once
"""
class TilingKinematics():
    def __init__(self):
        pass
    def Init_node(self):
        rospy.init_node("tile_just_kinematics")
        pub = rospy.Publisher("/ur_driver/URScript", String, queue_size=10)
        arduniopub = rospy.Publisher("/toggle_led", Empty, queue_size=10)
        return arduniopub,pub

    def moveur(self,q, ace, vel, t):
        ss = "movej([" + str(q[0]) + "," + str(q[1]) + "," + str(q[2]) + "," + str(q[3]) + "," + str(q[4]) + "," + str(
            q[5]) + "]," + "a=" + str(ace) + "," + "v=" + str(vel) + "," + "t=" + str(t) + ")"
        print ss
        # pub.publish(ss)
        return ss

    def get_T_translation(self,T):
        trans_x = T[3]
        trans_y = T[7]
        trans_z = T[11]
        return [trans_x, trans_y, trans_z]
    """
    T.translation is the marker coordinate in base frame,T.Rotaion is the posture in base frame
    level is the layer of tiles,such as 2x2,level=2,3x3,level=3
    """
    def caculating_path_to_pose(self,level,T):
        trans0=[T[3],T[7],T[11]]
        x0=T[3]
        y0=T[7]
        z0=T[11]
        result=[]
        for i in xrange(level):
            if i % 2==0 and i != 0:#even number
                for ii in xrange(level):
                    result.append([x0+0.155,y0-0.055*ii,z0+0.11*(i-1)])
            elif i%2 !=0:#odd number
                for ii in range(level)[::-1]:
                    result.append([x0+0.155,y0-0.055*ii,z0+0.055*i])
            else:
                for ii in xrange(level):
                    result.append([x0+0.155,y0-0.055*ii,z0])
        # print result
        all_result=[]

        for i in xrange(len(result)):
            temp = []
            print "level"+str(i)+"layer"+str(result[i])
            for j in xrange(len(T)):

                if j==3:
                    temp.append(result[i][0])
                elif j==7:
                    temp.append(result[i][1])
                elif j==11:
                    temp.append(result[i][2])
                else:
                    temp.append(T[j])
            all_result.append(temp)

        return all_result
    """
    ur0:kinematics attribute
    """
    def get_IK_from_T(self,ur0, T, q_last):
        weights = [1.] * 6
        return ur0.best_sol(weights, q_last, T)

    def insert_new_xy(self,T, nx, ny, nz):
        temp = []
        for i in xrange(16):
            if i == 3:
                temp.append(nx)
            elif i == 7:
                temp.append(ny)
            elif i == 11:
                temp.append(nz)
            else:
                temp.append(T[i])
        return temp

    def change_angle_to_pi(self,qangle):
        temp=[]
        for i in xrange(len(qangle)):
            temp.append(qangle[i]/180.0*3.14)
        return temp
    # def cacu_all_joint_path(self):
    """
    allpath: tiling path planning
    """
    # def caculate_all_tile_to_wall(self,allpath):
    def object_sucker(self,q,ur0):

        To=ur0.Forward(q)
        x0=To[3]
        y0=To[7]
        z0=To[11]
        newTo=self.insert_new_xy(To,x0,y0,z0-0.1)
        suckerq=self.get_IK_from_T(ur0,newTo,q)
        return suckerq
"""

        # print T0
        # arduniopub.publish(Empty())
        # time.sleep(0.5)
        # arduniopub.publish(Empty())
"""
def main():
    tilekinematic=TilingKinematics()
    arduniopub,urpub=tilekinematic.Init_node()
    # ar_sub = rospy.Subscriber("/ar_pose_marker", AlvarMarkers, ar_reader.callback)
    urt = 0
    # vel=0.1
    # ace=50
    ace = 1.4
    vel = 1.05
    weights = [1.] * 6
    #desirejoint = [-164.77, -95.48, -85.66, 3.99, 79.48, 136.22]#

    """
    desire joint
    """
    desirejoint=[-164.79,-99.49,-103.06,25.48,79.39,136.14]
    newdesirejoint = tilekinematic.change_angle_to_pi(desirejoint)
    # print newdesirejoint
    """
    tiling joint
    """

    """
    object joint
    """
    pickjoint = [-68.32,-116.71,-100.02,-52.65,88.09,158.76]
    newpickjoint = tilekinematic.change_angle_to_pi(pickjoint)

    """
    sucking joint
    """
    picksuckerq=[-68.32,-120.81,-102.02,-46.56,88.09,158.76]
    newpicksuckerq = tilekinematic.change_angle_to_pi(picksuckerq)
    # print newpickjoint
    # print newpicksuckerq
    urkinematics = Kinematic()

    T0 = urkinematics.Forward(newdesirejoint)
    # print numpy.array(T0).reshape(4,4)
    path = tilekinematic.caculating_path_to_pose(4, T0)
    all_path =[]
    # print path
    temp=newdesirejoint
    for i in path:
        # print i
        print "------------------"
        kk=tilekinematic.get_IK_from_T(urkinematics,i,temp)
        all_path.append(kk.tolist())
        # print kk.tolist()
        temp=kk.tolist()
    print len(all_path)
    # print T0
    # T0 = urkinematics.Forward(newpickjoint)
    # print T0
    rate=rospy.Rate(1)
    count_tile=0
    sucking_flags=0
    count_main=0
    while not rospy.is_shutdown():
        # arduniopub.publish(Empty())
        # time.sleep(1)
        if sucking_flags==0:


            # time.sleep(1.5)
            if count_main>=1:#di er ge loop caihui publish
                # sucking_flags=1
                mvstring = tilekinematic.moveur(newpicksuckerq, ace, vel, urt)
                urpub.publish(mvstring)
                arduniopub.publish(Empty())
                time.sleep(1.5)
                mvstring1 = tilekinematic.moveur(newdesirejoint, ace, vel, urt)
                urpub.publish(mvstring1)
                time.sleep(3.5)
                print "tile----------------->"+str(count_tile),all_path[count_tile]
                mvstring1 = tilekinematic.moveur(all_path[count_tile], ace, vel, urt)#tiling
                urpub.publish(mvstring1)

                time.sleep(3.5)
                arduniopub.publish(Empty())
                mvstring1 = tilekinematic.moveur(newdesirejoint, ace, vel, urt)#back some z aix
                urpub.publish(mvstring1)
                time.sleep(1.5)
                mvstring1 = tilekinematic.moveur(newpickjoint, ace, vel, urt)#back object
                urpub.publish(mvstring1)
                time.sleep(3.5)
                count_tile+=1
                if count_tile==16:
                    sucking_flags=1
                    print "tile all tiles-------"
            # print count_main
        else:
            print "over----",count_main
        count_main+=1
        # if count_tile<len(all_path):
        #     print "count_tile", count_tile
        #     mvstring=tilekinematic.moveur(all_path[count_tile],ace,vel,urt)
        #     print mvstring
        #     urpub.publish(mvstring)
        #     time.sleep(1.5)
        #     count_tile+=1
        #
        # else:
        #     print "tiling is over------"
        rate.sleep()
if __name__ == "__main__":
    main()
