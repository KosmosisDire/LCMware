/* LCM type definition class file
 * This file was automatically generated by lcm-gen
 * DO NOT MODIFY BY HAND!!!!
 * lcm-gen 1.5.1
 */

package examples;
 
import java.io.*;
import java.util.*;
import lcm.lcm.*;
 
/**
 * Joint trajectory point for action demo
 */
public final class JointTrajectoryPoint implements lcm.lcm.LCMEncodable
{
    public int num_positions;

    /**
     * LCM Type: double[num_positions]
     */
    public double positions[];

    /**
     * LCM Type: double[num_positions]
     */
    public double velocities[];

    /**
     * LCM Type: double[num_positions]
     */
    public double accelerations[];

    public double time_from_start;

 
    public JointTrajectoryPoint()
    {
    }
 
    public static final long LCM_FINGERPRINT;
    public static final long LCM_FINGERPRINT_BASE = 0x31e4435a33c6e651L;
 
    static {
        LCM_FINGERPRINT = _hashRecursive(new ArrayList<Class<?>>());
    }
 
    public static long _hashRecursive(ArrayList<Class<?>> classes)
    {
        if (classes.contains(examples.JointTrajectoryPoint.class))
            return 0L;
 
        classes.add(examples.JointTrajectoryPoint.class);
        long hash = LCM_FINGERPRINT_BASE
            ;
        classes.remove(classes.size() - 1);
        return (hash<<1) + ((hash>>63)&1);
    }
 
    public void encode(DataOutput outs) throws IOException
    {
        outs.writeLong(LCM_FINGERPRINT);
        _encodeRecursive(outs);
    }
 
    public void _encodeRecursive(DataOutput outs) throws IOException
    {
        outs.writeInt(this.num_positions); 
 
        for (int a = 0; a < this.num_positions; a++) {
            outs.writeDouble(this.positions[a]); 
        }
 
        for (int a = 0; a < this.num_positions; a++) {
            outs.writeDouble(this.velocities[a]); 
        }
 
        for (int a = 0; a < this.num_positions; a++) {
            outs.writeDouble(this.accelerations[a]); 
        }
 
        outs.writeDouble(this.time_from_start); 
 
    }
 
    public JointTrajectoryPoint(byte[] data) throws IOException
    {
        this(new LCMDataInputStream(data));
    }
 
    public JointTrajectoryPoint(DataInput ins) throws IOException
    {
        if (ins.readLong() != LCM_FINGERPRINT)
            throw new IOException("LCM Decode error: bad fingerprint");
 
        _decodeRecursive(ins);
    }
 
    public static examples.JointTrajectoryPoint _decodeRecursiveFactory(DataInput ins) throws IOException
    {
        examples.JointTrajectoryPoint o = new examples.JointTrajectoryPoint();
        o._decodeRecursive(ins);
        return o;
    }
 
    public void _decodeRecursive(DataInput ins) throws IOException
    {
        this.num_positions = ins.readInt();
 
        this.positions = new double[(int) num_positions];
        for (int a = 0; a < this.num_positions; a++) {
            this.positions[a] = ins.readDouble();
        }
 
        this.velocities = new double[(int) num_positions];
        for (int a = 0; a < this.num_positions; a++) {
            this.velocities[a] = ins.readDouble();
        }
 
        this.accelerations = new double[(int) num_positions];
        for (int a = 0; a < this.num_positions; a++) {
            this.accelerations[a] = ins.readDouble();
        }
 
        this.time_from_start = ins.readDouble();
 
    }
 
    public examples.JointTrajectoryPoint copy()
    {
        examples.JointTrajectoryPoint outobj = new examples.JointTrajectoryPoint();
        outobj.num_positions = this.num_positions;
 
        outobj.positions = new double[(int) num_positions];
        if (this.num_positions > 0)
            System.arraycopy(this.positions, 0, outobj.positions, 0, (int) this.num_positions); 
        outobj.velocities = new double[(int) num_positions];
        if (this.num_positions > 0)
            System.arraycopy(this.velocities, 0, outobj.velocities, 0, (int) this.num_positions); 
        outobj.accelerations = new double[(int) num_positions];
        if (this.num_positions > 0)
            System.arraycopy(this.accelerations, 0, outobj.accelerations, 0, (int) this.num_positions); 
        outobj.time_from_start = this.time_from_start;
 
        return outobj;
    }
 
}

