/* LCM type definition class file
 * This file was automatically generated by lcm-gen
 * DO NOT MODIFY BY HAND!!!!
 * lcm-gen 1.5.1
 */

package core;
 
import java.io.*;
import java.util.*;
import lcm.lcm.*;
 
public final class EmptyResponse implements lcm.lcm.LCMEncodable
{
    public core.ResponseHeader response_header;

 
    public EmptyResponse()
    {
    }
 
    public static final long LCM_FINGERPRINT;
    public static final long LCM_FINGERPRINT_BASE = 0xbbccb38ab2d0c608L;
 
    static {
        LCM_FINGERPRINT = _hashRecursive(new ArrayList<Class<?>>());
    }
 
    public static long _hashRecursive(ArrayList<Class<?>> classes)
    {
        if (classes.contains(core.EmptyResponse.class))
            return 0L;
 
        classes.add(core.EmptyResponse.class);
        long hash = LCM_FINGERPRINT_BASE
             + core.ResponseHeader._hashRecursive(classes)
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
        this.response_header._encodeRecursive(outs); 
 
    }
 
    public EmptyResponse(byte[] data) throws IOException
    {
        this(new LCMDataInputStream(data));
    }
 
    public EmptyResponse(DataInput ins) throws IOException
    {
        if (ins.readLong() != LCM_FINGERPRINT)
            throw new IOException("LCM Decode error: bad fingerprint");
 
        _decodeRecursive(ins);
    }
 
    public static core.EmptyResponse _decodeRecursiveFactory(DataInput ins) throws IOException
    {
        core.EmptyResponse o = new core.EmptyResponse();
        o._decodeRecursive(ins);
        return o;
    }
 
    public void _decodeRecursive(DataInput ins) throws IOException
    {
        this.response_header = core.ResponseHeader._decodeRecursiveFactory(ins);
 
    }
 
    public core.EmptyResponse copy()
    {
        core.EmptyResponse outobj = new core.EmptyResponse();
        outobj.response_header = this.response_header.copy();
 
        return outobj;
    }
 
}

