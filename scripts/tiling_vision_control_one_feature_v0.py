#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
import numpy,math
import Quaternion as Q
import time
from numpy import linalg
import yaml
import os
from urdf_parser_py.urdf import URDF
from pykdl_utils.kdl_parser import kdl_tree_from_urdf_model
from pykdl_utils.kdl_kinematics import KDLKinematics

from ur5_planning.msg import uv
from ur5_planning.msg import tileuv
from sensor_msgs.msg import JointState
from ur5_pose_get import *
from std_msgs.msg import UInt16,Float64

from std_msgs.msg import String
from Functions_for_other_py import *
"""
os.system("rostopic pub io_state std_msgs/String "55C8010155" --once")
"""
class TilingVisionControl():
    def __init__(self,nodename,urdfname,detat,lamda,califilename,camf,kappa=0.7,delta=5):
        self.nodename=nodename
        self.califilename=califilename
        self.urdfname=urdfname
        self.camf=camf
        self.detat=detat
        self.kappa=kappa
        self.delta=delta
        self.lamda=lamda

        self.tile_0_buf=[]
        self.tile_1_buf = []
        self.ledstate=None
        self.changeuv=None
        self.w_pub = rospy.Publisher("/w_param", Float64, queue_size=10)
    def Init_node(self):
        rospy.init_node(self.nodename)
        # tile_reader = TileUvRead()
        tileuv_sub = rospy.Subscriber("/tile_uv", tileuv, self.callback)
        ur_pub = rospy.Publisher("/ur_driver/URScript", String, queue_size=10)
        return ur_pub
    """
    0:o
    1:d
    """
    def callback(self, msg):
        if msg.tile_id == 0:
            if len(self.tile_0_buf) == 10:
                self.tile_0_buf = self.tile_0_buf[1:]
                tile_id = msg.tile_id
                cen_uv = msg.cen_uv
                f1th_uv = msg.f1th_uv
                s2th_uv = msg.s2th_uv
                t3th_uv = msg.t3th_uv
                f4th_uv = msg.f4th_uv
                self.tile_0_buf.append(
                    [tile_id, cen_uv.uvinfo, f1th_uv.uvinfo, s2th_uv.uvinfo, t3th_uv.uvinfo, f4th_uv.uvinfo])
                # print "---------self.uvlist_buf",self.uvlist_buf
            else:
                tile_id = msg.tile_id
                cen_uv = msg.cen_uv
                f1th_uv = msg.f1th_uv
                s2th_uv = msg.s2th_uv
                t3th_uv = msg.t3th_uv
                f4th_uv = msg.f4th_uv
                self.tile_0_buf.append(
                    [tile_id, cen_uv.uvinfo, f1th_uv.uvinfo, s2th_uv.uvinfo, t3th_uv.uvinfo, f4th_uv.uvinfo])
        else:
            print "wait opencv caulate tile uv ----"
            time.sleep(1)
        # print " msg.tile_id", msg.tile_id

    def Get_ur_X(self,info):

        aa = Get_X_from_cali_quaternion(info)
        aa = numpy.mat(aa)
        # print "X", aa
        return aa.reshape((4, 4))
    def get_jacabian_from_joint(self,urdfname,jointq):
        robot = URDF.from_xml_file(urdfname)
        tree = kdl_tree_from_urdf_model(robot)
        # print tree.getNrOfSegments()
        chain = tree.getChain("base_link", "ee_link")
        # print chain.getNrOfJoints()
        # forwawrd kinematics
        kdl_kin = KDLKinematics(robot, "base_link", "ee_link")
        q=jointq
        #q = [0, 0, 1, 0, 1, 0]
        pose = kdl_kin.forward(q)  # forward kinematics (returns homogeneous 4x4 matrix)
        # # print pose
        # #print list(pose)
        # q0=Kinematic(q)
        # if flag==1:
        #     q_ik=q0.best_sol_for_other_py( [1.] * 6, 0, q0.Forward())
        # else:
        #     q_ik = kdl_kin.inverse(pose)  # inverse kinematics
        # # print "----------iverse-------------------\n", q_ik
        #
        # if q_ik is not None:
        #     pose_sol = kdl_kin.forward(q_ik)  # should equal pose
        #     print "------------------forward ------------------\n",pose_sol

        J = kdl_kin.jacobian(q)
        #print 'J:', J
        return J,pose
    def get_cam_data(self):
        f=open(self.califilename)
        yamldata=yaml.load(f)
        #print yamldata
        kx =  yamldata['camera_matrix']['data'][0]
        #print kx
        ky = yamldata['camera_matrix']['data'][4]
        #print ky
        u0=yamldata['camera_matrix']['data'][2]
        v0 = yamldata['camera_matrix']['data'][5]
        cam = {'kx': kx, 'ky': ky, "u0": u0, "v0": v0}
        return cam
    def vis2jac(self,uv,z):
        cam=self.get_cam_data()
        rh0=[0.0000032,0.0000032]
        camf=self.camf#m
        kx = cam['kx']
        ky = cam['ky']
        arfx=kx/camf
        arfy=ky/camf
        # kx=arfx*camf
        # ky=arfy*camf
        uba=uv[0]-cam['u0']
        vba=uv[1]-cam['v0']
        L=[[-arfx/z,0,uba/z,1/arfx*uba*vba,-(arfx**2+uba**2)/arfx,vba,0,-arfy/z,vba/z,(arfy**2+vba**2)/arfy,-uba*vba/arfx,-uba]]
        J=numpy.array(L).reshape((2,6))
        return J
    #uv more than one
    #,uv = [[672, 672], [632, 662]]
    def vis2jac_mt1(self,uvm,z):
        if len(uvm)>1:
            L=self.vis2jac(uvm[0],z)
            #L=numpy.array(L).reshape((2,6))
            for i in xrange(1,len(uvm)):
                J=numpy.row_stack((L,self.vis2jac(uvm[i],z)))
                #print "-------",i,J
                L=J
            #print "vision jacobian last\n",J
            return J
        else:
            return self.vis2jac(uvm[0],z)

    def get_feature_error(self,desireuv,nowuv):
        kk=numpy.mat(nowuv).T-numpy.mat(desireuv).T
        return kk.reshape((1,2))

    #cam speed (udot,vdot)(xdot,ydot,zdot,wxdot,wydot,wzdot)
    #get camera frame speed,you must change to ee frame
    #uvm means now uv
    def get_cam_vdot(self,uvm,z,desireuv,nowuv):
        J=self.vis2jac_mt1(uvm,z)
        JJ=numpy.linalg.pinv(J)
        e=self.get_feature_error(desireuv,nowuv)
        vdot=self.lamda*numpy.dot(JJ,e.T)
        return vdot

    #samebody tranlasition to jacbian
    #joint speed (q0dot,q1dot,q2dot,q3dot,q4dot,q5dot)
    # def get_joint_speed(self,uvm,z,desireuv,nowuv,q,info):
    #     #1,get base to ee jacabian
    #     Jacabian_joint,pose=self.get_jacabian_from_joint(self.urdfname,q)
    #     # print ""
    #     #2,get ee(AX=XB) to camera frame jacabian
    #     X=self.Get_ur_X(info)#numpu array
    #     #tr2jac
    #     jac = tr2jac(X,1)
    #     #print "------X",X
    #     inv_X_jac = jac.I
    #     #get ee speed
    #     #print "tr2jac-----\n",jac
    #     cam_speed = self.get_cam_vdot(uvm, z, desireuv, nowuv)
    #     # print "cam_speed--------\n",cam_speed
    #     ee_speed = numpy.dot(inv_X_jac, cam_speed)
    #     # print "ee_speed-----before changing--------\n",ee_speed
    #     v_list = ee_speed.reshape((1, 6)).tolist()[0]
    #     flag_list = [0, 1, 1, 0, 0, 0]
    #     vdot_z = [1.0 * v_list[i] * flag_list[i] for i in range(6)]
    #     # print("ee_speed_after--------------\n",vdot_z)
    #     j_speed=numpy.dot(Jacabian_joint.I,numpy.mat(vdot_z).T)
    #     return j_speed
    def get_joint_speed(self,uvm,z,desireuv,nowuv,q,info):
        #1,get base to ee jacabian
        Jacabian_joint,T_06=self.get_jacabian_from_joint(self.urdfname,q)
        #2,get ee(AX=XB) to camera frame jacabian
        X=self.Get_ur_X(info)#numpu array
        ebT=T_06
        #tr2jac
        jac = tr2jac(X,1)
        jac_b2e=tr2jac(T_06,0)
        #print "------X",X
        inv_X_jac = jac.I
        #get ee speed
        #print "tr2jac-----\n",jac
        cam_speed = self.get_cam_vdot(uvm, z, desireuv, nowuv)
        print "cam_speed--------",cam_speed
        ee_speed_in_eeframe = numpy.dot(inv_X_jac, cam_speed)
        v_list = ee_speed_in_eeframe.reshape((1, 6)).tolist()[0]
        #[z,y,]
        flag_list = [0, 1, 1, 0, 0, 0]
        vdot_z = [1.0 * v_list[i] * flag_list[i] for i in range(6)]
        ee_speed_in_base = numpy.dot(jac_b2e.I, numpy.mat(vdot_z).T)
        print "ee_speed-----before changing--------",ee_speed_in_base

        print("ee_speed_after--------------\n",vdot_z)
        j_speed=numpy.dot(Jacabian_joint.I,ee_speed_in_base)
        return j_speed
    def get_deta_joint_angular(self,j_speed):
        #print j_speed
        joint_angular=float(self.detat)*numpy.array(j_speed)
        #print '-------joint_angular-----\n',joint_angular
        return joint_angular

    def get_joint_angular(self,qnow,detajoint):
        #result=[]
        listangular=[]
        for i in range(len(detajoint.tolist())):
            listangular.append(detajoint.tolist()[i][0]+qnow[i])
        # print "list",detajoint.tolist()
        return listangular

    def ibvs_run_ur5(self,uvm,z,q,info):

        """
        First,Get the uv to drive ur5
        x=uvm[0]=nowuv

        """
        xp=self.tile_0_buf[-1][1]
        """
        Second,caculating cam vodt and deta joint speed
        desireuv=xp
        """

        joint_speed_dot=self.get_joint_speed(uvm, z, xp, uvm[0], q, info)
        print "joint_speed_dot",joint_speed_dot
        """
        Third,caculating deta joint speed
        """
        deta_joint_angular=self.get_deta_joint_angular(joint_speed_dot)
        print "deta_joint_angular",deta_joint_angular
        """
        Fourth,get joint angular
        """
        pub_joint=self.get_joint_angular(q, deta_joint_angular)
        print "pub_joint",pub_joint
        return pub_joint

    def Move_ur(self,q_pub_now,ace,vel,urt):
        ss = "movej([" + str(q_pub_now[0]) + "," + str(q_pub_now[1]) + "," + str(q_pub_now[2]) + "," + str(
            q_pub_now[3]) + "," + str(q_pub_now[4]) + "," + str(q_pub_now[5]) + "]," + "a=" + str(
            ace) + "," + "v=" + str(
            vel) + "," + "t=" + str(urt) + ")"
        return ss
    def Open_sucking_close_IoBoard(self,flag):
        Protocol="55C8010"+str(flag)+"55"
        Pub_str='rostopic pub io_state std_msgs/String '+Protocol+' --once'
        os.system(Pub_str)
    def Open_sucking_close_Ardunio(self):
        Protocol="{}"
        Pub_str='rostopic pub /toggle_led std_msgs/Empty '+Protocol+' --once'
        os.system(Pub_str)

def main():
    #uvlist=[123.0,112.0]
    uvlist=[]
    camf=624.0429 * 1e-03
    # uvcentral=[316,251]
    uvcentral = [338, 76]#sucking central
    First_joint_angular=[]
    calibinfo=[
        0.109982645426,
        0.114476746567,
        -0.0415924235801,
        0.249492772999,
        0.523487628443,
        0.239612281752,
        0.778652691205
    ]
    urdfname = "/data/ros/ur_ws_yue/src/tilling_robot/urdf/ur5.urdf"
    cailename = "/data/ros/ur_ws_yue/src/tilling_robot/yaml/cam_500_logitech.yaml"
    nodename="tilling_vision_control"
    ace=50
    vel=0.1
    urt=0
    detat=0.05
    ratet=30
    lamda=3.666666
    z=0.45
    ur_reader = Urposition()
    ur_sub = rospy.Subscriber("/joint_states", JointState, ur_reader.callback)
    u_error_pub = rospy.Publisher("/object_feature_u_error", Float64, queue_size=10)
    v_error_pub = rospy.Publisher("/object_feature_v_error", Float64, queue_size=10)
    """
    Those two flag use to make sucker sucking tile
    """
    object_flag=0
    open_desire_flag= 0
    desire_flag=0
    """
    nodename,urdfname,delta,kappa,lamda,califilename,camf)
    """
    F0=TilingVisionControl(nodename,urdfname,detat,lamda,cailename,camf)
    ur_pub=F0.Init_node()
    rate = rospy.Rate(ratet)
    First_joint_angular = ur_reader.ave_ur_pose

    Object_joint_angular_vision_state=[]
    Object_joint_angular_sucking_state = [-68.91,-98.86,-81.19,-89.11,89.35,91.79]

    Desire_joint_angular_vision_state=[]
    Desire_joint_angular_place_state = [266.09, -178.29, 117.69, -121.76, -267.38, -216.20]

    print "First_joint_angular",First_joint_angular
    while not rospy.is_shutdown():
        try:
            """
            First,Go to object position,just need opreating tile 0,
            Now UV also is [316,251]
            """
            q_now = ur_reader.ave_ur_pose
            print "q_now",q_now
            if len(q_now) != 0:
                if len(F0.tile_0_buf)!=0:
                    uvm = [uvcentral]
                    q_pub_now=F0.ibvs_run_ur5(uvm,z,q_now,calibinfo)
                    MoveUrString=F0.Move_ur(q_pub_now, ace, vel, urt)
                    ur_pub.publish(MoveUrString)
                    print "F0.tile_0_buf",F0.tile_0_buf[-1]
            else:
                print "UR5 is Not Ok,Please check"
        except KeyboardInterrupt:
            sys.exit()

        rate.sleep()
if __name__=="__main__":
    main()

